# -*- coding: utf-8 -*-
from datetime import datetime
from openerp import models, fields, api, tools, SUPERUSER_ID
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
import openerp.addons.decimal_precision as dp
import pytz


class br_product_pricelist_item(models.Model):
    _inherit = 'product.pricelist.item'

    _applied_on_field_map = {
        '0_product_variant': 'product_id',
        '1_product': 'product_tmpl_id',
        '2_product_category': 'categ_id',
        '4_menu_name': 'menu_id'
    }

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        # if self.env.context.get('menu_name_id', False):
        args.extend(['|', ('pricelist_id.company_id', '=', self.env.user.company_id.id), ('pricelist_id.company_id', '=', False)])
        return super(br_product_pricelist_item, self).search(args, offset=offset, limit=limit, order=order, count=count)

    @api.model
    def create(self, vals):
        if 'recipes_ids' in vals and vals['applied_on'] == '4_menu_name':
            price = 0
            for line in vals['recipes_ids']:
                if line[2]:
                    price += line[2]['times'] * line[2]['fix_price'] * line[2]['quantity']
            vals['fixed_price'] = price
        res = super(br_product_pricelist_item, self).create(vals)
        return res

    @api.one
    def write(self, vals):
        if 'recipes_ids' in vals:
            price = 0
            for line in vals['recipes_ids']:
                item = False
                times = 0
                fix_price = 0
                quantity = 0
                if line[0] not in (2, 5):  # 2, 5 are delete commands
                    if line[1]:
                        item = self.env['br.pricelist.recipes'].browse(line[1])
                        times = item.times
                        fix_price = item.fix_price
                        quantity = item.quantity
                    if len(line) > 2 and line[2]:
                        if 'times' in line[2]:
                            times = line[2]['times'] or 0
                        if 'fix_price' in line[2]:
                            fix_price = line[2]['fix_price'] or 0
                        if 'quantity' in line[2]:
                            quantity = line[2]['quantity'] or 0
                    price += times * fix_price * quantity
            vals['fixed_price'] = price
        res = super(br_product_pricelist_item, self).write(vals)
        return res

    @api.one
    @api.depends('categ_id', 'product_tmpl_id', 'product_id', 'menu_id', 'compute_price', 'fixed_price', \
                 'pricelist_id', 'percent_price', 'price_discount', 'price_surcharge')
    def _get_pricelist_item_name_price(self):
        if self.categ_id:
            self.name = _("Category: %s") % (self.categ_id.name)
        elif self.product_tmpl_id:
            self.name = self.product_tmpl_id.name
        elif self.menu_id:
            self.name = self.menu_id.name
            price = 0
            for line in self.recipes_ids:
                price += line.times * line.fix_price * line.quantity
            self.fixed_price = price
        elif self.product_id:
            self.name = self.product_id.display_name.replace('[%s]' % self.product_id.code, '')
        else:
            self.name = _("All Products")

        if self.compute_price == 'fixed':
            self.price = ("%s %s") % (self.fixed_price, self.pricelist_id.currency_id.name)
        elif self.compute_price == 'percentage':
            self.price = _("%s %% discount") % (self.percent_price)
        else:
            self.price = _("%s %% discount and %s surcharge") % (abs(self.price_discount), self.price_surcharge)

    applied_on = fields.Selection(
        [('4_menu_name', 'Menu Name'), ('3_global', 'Global'), ('2_product_category', ' Product Category'),
         ('1_product', 'Product'),
         ('0_product_variant', 'Product Variant')], string="Apply On", required=True, default='4_menu_name',
        help='Pricelist Item applicable on selected option')

    menu_id = fields.Many2one('product.product', string='Menu Name')

    recipes_ids = fields.One2many('br.pricelist.recipes', 'pricelist_item_id', string="Recipes", copy=True)

    @api.onchange('applied_on')
    def _onchange_applied_on(self):
        for applied_on, field in self._applied_on_field_map.iteritems():
            if self.applied_on != applied_on:
                setattr(self, field, False)

    @api.onchange('menu_id')
    def onchange_menu_name(self):
        res = []
        # if self.recipes_ids:
        #     res = [(2, i.id, False) for i in self.recipes_ids]

    # if not self.recipes_ids:
        recipes = self.menu_id.product_recipe_lines
        for recipe in recipes:
            times = recipe.times
            quantity = recipe.product_qty
            apply_for = recipe.applied_for
            if apply_for == 'product':
                product_ids = []
                for line in recipe.rule_ids:
                    product_ids.append((4, line.product_id.id, None))
                res.append((0, 0, {
                    'times': times,
                    'quantity': quantity,
                    'product_ids': product_ids,
                    'menu_recipe_id': recipe.id
                }))
            else:
                categ_ids = []
                for line in recipe.categ_ids:
                    categ_ids.append((4, line.id, None))
                res.append((0, 0, {
                    'times': times,
                    'quantity': quantity,
                    'categ_ids': categ_ids,
                    'menu_recipe_id': recipe.id
                }))
        self.recipes_ids = res
        self.product_id = self.menu_id.id

class br_pricelist_memu_name(models.Model):
    _name = 'br.pricelist.recipes'

    categ_ids = fields.Many2many(
        'product.category',
        string='Categories',
        help='Get categories from rule of this menu name.')
    product_ids = fields.Many2many(
        'product.product',
        string='Products',
        help='Get products from rule of this menu name')
    fix_price = fields.Float(string="Fix Price", digits=dp.get_precision('Product Price'))
    times = fields.Float(string="Times")
    quantity = fields.Float(string="Quantity")
    pricelist_item_id = fields.Many2one('product.pricelist.item', string="Pricelist Item")
    # menu_recipe_id = fields.Many2one('br.menu.name.recipe', string="Menu Name Recipe")


class br_product_pricelist(models.Model):
    _inherit = "product.pricelist"

    # @api.model
    # def _price_rule_get_multi(self, pricelist, products_by_qty_by_partner):
    #     context = self.env.context
    #     context = dict(context or {})
    #     # context.update({
    #     #     'menu_name': 7
    #     # })
    #     if 'menu_name' in context and context.get('menu_name'):
    #         menu_name = context.get('menu_name')
    #         date = context.get('date') and context['date'][0:10] or time.strftime(DEFAULT_SERVER_DATE_FORMAT)
    #         # products = map(lambda x: x[0], products_by_qty_by_partner)
    #         product_uom_obj = self.pool.get('product.uom')
    #         #
    #         # if not products:
    #         #     return {}
    #         # prod_ids = [product.id for product in products]
    #
    #         # Load all rules
    #         cr = self.env.cr
    #         cr.execute(
    #             '''SELECT i.id
    #             FROM product_pricelist_item AS i
    #             WHERE menu_id  = %s
    #             AND (pricelist_id = %s)
    #             AND ((i.date_start IS NULL OR i.date_start<='%s') AND (i.date_end IS NULL OR i.date_end>='%s'))'''
    #             % (menu_name, pricelist.id, date, date))
    #
    #         item_ids = [x[0] for x in cr.fetchall()]
    #         items = self.env['product.pricelist.item'].browse(item_ids)
    #         results = {}
    #         for product, qty, partner in products_by_qty_by_partner:
    #             results[product.id] = 0.0
    #             suitable_rule = False
    #
    #             # Final unit price is computed according to `qty` in the `qty_uom_id` UoM.
    #             # An intermediary unit price may be computed according to a different UoM, in
    #             # which case the price_uom_id contains that UoM.
    #             # The final price will be converted to match `qty_uom_id`.
    #             qty_uom_id = context.get('uom') or product.uom_id.id
    #             price_uom_id = product.uom_id.id
    #             qty_in_product_uom = qty
    #             if qty_uom_id != product.uom_id.id:
    #                 try:
    #                     qty_in_product_uom = product_uom_obj._compute_qty(
    #                         context['uom'], qty, product.uom_id.id)
    #                 except UserError:
    #                     # Ignored - incompatible UoM in context, use default product UoM
    #                     pass
    #
    #             # if Public user try to access standard price from website sale, need to call _price_get.
    #             price = self.env['product.product'].browse(menu_name).product_tmpl_id.list_price
    #             # price_uom_id = qty_uom_id
    #             for rule in items:
    #                 suitable_rule = rule
    #                 cr.execute('''select A.fix_price from br_pricelist_recipes A inner join br_pricelist_recipes_product_product_rel B on A.id = B.br_pricelist_recipes_id
    #                         where B.product_product_id = %s and A.pricelist_item_id = %s    ''' % (product.id, rule.id))
    #                 item_ids = [x[0] for x in cr.fetchall()]
    #                 if len(item_ids) > 0:
    #                     price = item_ids[0]
    #                 else:
    #                     # categ_id = product.product_tmpl_id.categ_id
    #                     categ_id = context.get('product_category_id')
    #                     if categ_id:
    #                         cr.execute('''select A.fix_price from br_pricelist_recipes A inner join br_pricelist_recipes_product_category_rel B on A.id = B.br_pricelist_recipes_id
    #                                  where B.product_category_id = %s and A.pricelist_item_id = %s    ''' % (
    #                         categ_id, rule.id))
    #                         item_ids = [x[0] for x in cr.fetchall()]
    #                         if len(item_ids) > 0:
    #                             price = item_ids[0]
    #             # Final price conversion into pricelist currency
    #             # if suitable_rule and suitable_rule.compute_price != 'fixed' and suitable_rule.base != 'pricelist':
    #             #     price = self.env['res.currency'].compute(product.currency_id.id, pricelist.currency_id.id, price)
    #
    #             results[product.id] = (price, suitable_rule and suitable_rule.id or False)
    #         return results
    #     else:
    #         return super(br_product_pricelist, self)._price_rule_get_multi(pricelist, products_by_qty_by_partner)

    def get_current_date(self):
        tz = self.env.context.get('tz')
        if not tz:
            tz = self.sudo().env.user.tz or 'UTC'
        now = datetime.now(pytz.timezone(tz)).date()
        now_str = now.strftime(DEFAULT_SERVER_DATE_FORMAT)
        return now_str

    @api.model
    def get_ls_price(self):
        now_str = self.get_current_date()
        cr = self.env.cr
        # cr.execute(
        #     ''' select B.pricelist_id, B.menu_id, A.fix_price, D.product_product_id, E.id as rule_id  from br_pricelist_recipes A inner join product_pricelist_item B on A.pricelist_item_id = B.id
        #                inner join product_pricelist C on B.pricelist_id = C.id
			# 		   inner join br_pricelist_recipes_product_product_rel D on A.id = D.br_pricelist_recipes_id
			# 		   inner join br_menu_name_recipe E on E.id = A.menu_recipe_id
			# ''')
        cr.execute(
            '''
            select A2.pricelist_id, A1.product_menu_id, A2.fix_price, A1.product_id, A1.rule_id, A2.recipes_id, A2.times, A2.qty  from
            (
            select A.product_id, B.product_menu_id, B.id as rule_id, B.times, B.product_qty from br_product_group_rule A
            inner join br_menu_name_recipe B on A.line_id=B.id
            where B.product_menu_id is not null
            ) as A1
            inner join

            (select E.pricelist_id, C.product_product_id, E.menu_id as menu_id, D.id as recipes_id, D.times, D.quantity as qty, D.fix_price from br_pricelist_recipes_product_product_rel C
            inner join br_pricelist_recipes D on C.br_pricelist_recipes_id = D.id
            inner join product_pricelist_item E on D.pricelist_item_id=E.id 
            WHERE  (E.date_start IS NULL OR E.date_start<=%s)
                AND (E.date_end IS NULL OR E.date_end>=%s)
            ORDER BY E.date_start) as A2
            on A1.product_id = A2.product_product_id and A1.product_menu_id = A2.menu_id and A1.times=A2.times and A1.product_qty=A2.qty
            order by A2.recipes_id
            ''', (now_str, now_str))
        item_ids = [(x[0], x[1], x[2], x[3], x[4]) for x in cr.fetchall()]
        return item_ids

    @api.model
    def get_ls_price_categ(self):
        now_str = self.get_current_date()
        cr = self.env.cr
        # cr.execute(
        #     ''' select B.pricelist_id, B.menu_id, A.fix_price, D.product_category_id from br_pricelist_recipes A inner join product_pricelist_item B on A.pricelist_item_id = B.id
        #                inner join product_pricelist C on B.pricelist_id = C.id
        #                inner join br_pricelist_recipes_product_category_rel D on A.id = D.br_pricelist_recipes_id
        #     ''')
        cr.execute(
            '''
            select A2.pricelist_id, A1.product_menu_id, A2.fix_price, A1.product_category_id, A1.rule_id, A2.recipes_id, A2.times, A2.qty from
            (select A.product_category_id, B.product_menu_id, B.id as rule_id, B.times, B.product_qty as qty from br_menu_name_recipe_product_category_rel A
            inner join br_menu_name_recipe B on A.br_menu_name_recipe_id=B.id
            where B.product_menu_id is not null
            ) as A1
            inner join

            (select E.pricelist_id, C.product_category_id, E.menu_id as menu_id, D.id as recipes_id, D.times, D.quantity as qty, D.fix_price from br_pricelist_recipes_product_category_rel C
            inner join br_pricelist_recipes D on C.br_pricelist_recipes_id = D.id
            inner join product_pricelist_item E on D.pricelist_item_id=E.id
            WHERE  (E.date_start IS NULL OR E.date_start<=%s)
                AND (E.date_end IS NULL OR E.date_end>=%s)
            ORDER BY E.date_start) as A2
            on A1.product_category_id = A2.product_category_id and A1.product_menu_id = A2.menu_id and A1.times=A2.times and A1.qty=A2.qty
            order by A2.recipes_id
            ''', (now_str, now_str))


        item_ids = [(x[0], x[1], x[2], x[3], x[4]) for x in cr.fetchall()]
        return item_ids