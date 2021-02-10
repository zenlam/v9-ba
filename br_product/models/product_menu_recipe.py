# -*- coding:utf-8 -*-
from openerp import fields, api, models


class product_menu_line(models.Model):
    _name = 'br.menu.name.recipe'

    _order = "sequence asc"

    name = fields.Char('Rule', size=100, required=True)
    times = fields.Integer('Times', default=1)
    product_id = fields.Many2one('product.product', 'Product', required=False)
    product_qty = fields.Float(string="Quantity", precision_digits=2)
    sequence = fields.Integer(string="Sequence")
    applied_for = fields.Selection([('product', 'Product'),
                                    ('category', 'Category'),
                                    ], string="Applied For", default="category")
    instruction = fields.Text(string="Instruction")
    is_topping = fields.Boolean(string="Is Topping")
    product_categ_id = fields.Many2one(
        'product.category', string='Add by Category')
    categ_ids = fields.Many2many(
        'product.category',
        string='Categories',
        help='If a category is chosen, whenever this rule is applicable to any product added to that category.')
    # product_menu_id = fields.Many2one(
    #     comodel_name='br.menu.name', string='Product')
    product_menu_id = fields.Many2one(
        comodel_name='product.product', string='Product', ondelete='cascade')
    rule_ids = fields.One2many(
        'br.product.group.rule', string='Products', inverse_name='line_id')
    # product_uom = fields.Many2one(comodel_name='product.uom', string='Product Unit of Measure', required=True,
    #                               help="Unit of Measure (Unit of Measure) is the unit of measurement for the inventory control")

    @api.multi
    def onchange_applied_for(self):
        return {
            'value': {'rule_ids': []}
        }

    def get_all_child(self, objs):
        list_child_id = []
        for obj in objs:
            list_child_id += self.get_all_child(obj.child_id)
            list_child_id.append(obj.id)
        return list_child_id

    def _get_rules(self, vals):
        ruleModel = self.env['br.product.group.rule']
        for r in vals:
            if r['applied_for'] == 'product':
                rules = ruleModel.search_read(domain=[('id', 'in', r['rule_ids'])], fields=['product_id', 'product_code'])
                for rule in rules:
                    rule['product_qty'] = r['product_qty']
                r.update({'rules': rules})
            else:
                all_categ_ids = self.get_all_child(
                    self.env['product.category'].search([('id', 'in', r['categ_ids'])]))
                r['categ_ids'] = all_categ_ids

    @api.model
    def search_read(
            self,
            domain=None,
            fields=None,
            offset=0,
            limit=None,
            order=None):
        res = super(
            product_menu_line,
            self).search_read(
            domain=domain,
            fields=fields,
            offset=offset,
            limit=limit,
            order=order)
        if self.env.context.get('load_rule', False):
            self._get_rules(res)
        return res

class product_menu_rule(models.Model):
    _name = 'br.product.group.rule'

    @api.one
    def _get_default_product_qty(self):
        if self.line_id and self.line_id.product_qty:
            return self.line_id.product_qty

    line_id = fields.Many2one('br.menu.name.recipe')
    product_id = fields.Many2one('product.product')
    product_code = fields.Char('Item Code', related='product_id.default_code')
    product_qty = fields.Float(
        'Quantity', readonly=True, default=_get_default_product_qty, precision_digits=2)
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string='Item',
        related='product_id.product_tmpl_id',
        store=False)
