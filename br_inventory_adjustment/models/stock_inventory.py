import itertools
import logging
import time
from datetime import datetime, timedelta

import openerp.addons.decimal_precision as dp

from common import STOCK_COUNT_TYPE, UOM_TYPE, GROUP_TYPE
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError, UserError
from openerp.osv import fields as Ofields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

# special columns automatically created by the ORM
LOG_ACCESS_COLUMNS = ['create_uid', 'create_date', 'write_uid', 'write_date']
MAGIC_COLUMNS = ['id'] + LOG_ACCESS_COLUMNS
_logger = logging.getLogger(__name__)


class StockInventory(models.Model):
    _name = 'stock.inventory'
    _inherit = ['stock.inventory', 'mail.thread', 'ir.needaction_mixin']

    def __init__(self, pool, cr):
        # Change 'done' state display string
        init_res = super(StockInventory, self).__init__(pool, cr)
        for i in range(len(self.INVENTORY_STATE_SELECTION)):
            if self.INVENTORY_STATE_SELECTION[i][0] == 'done':
                self.INVENTORY_STATE_SELECTION[i] = ('done', 'Unreviewed')
        return init_res

    state = fields.Selection(selection_add=[('official_acount_initiated', 'Official Count Initiated '),
                                            ('official_count_in_progress', 'Official Count In Progress'),
                                            ('1st_degree', '1st Degree'),
                                            ('2nd_degree', '2nd Degree'),
                                            ('no_case', 'No Case'),
                                            ], track_visibility='always')
    name = fields.Char(oldname='name', copy=False, default='/')
    is_from_unofficial = fields.Boolean(string="Is Create From Unofficial Count", default=False)
    stock_count_type = fields.Selection(selection=STOCK_COUNT_TYPE, string="Template Type")
    template_id = fields.Many2one(string="Template", comodel_name='stock.inventory.template', ondelete='restrict')
    warehouse_id = fields.Many2one(string="Warehouse/ Outlet", comodel_name='stock.warehouse')
    pic_id = fields.Many2one(string="PIC", comodel_name='res.users', default=lambda self: self.env.user)
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency',
                                  compute=lambda x: x.env.user.company_id.currency_id.id)
    summary_line_ids = fields.One2many(string="Summary", comodel_name='stock.inventory.summary',
                                       inverse_name='inventory_id',
                                       copy=False)
    summary_total = fields.Float(string="Total loss/gain", compute="_get_summary_total")
    line_unofficial_ids = fields.One2many(comodel_name='stock.inventory.line.unofficial', inverse_name='inventory_id')
    reviewer_id = fields.Many2one(string="Reviewer", comodel_name='res.users')
    manage_expirydate = fields.Boolean(string="Count By Expiry Date", default=True)
    location_manage_expirydate = fields.Boolean(related='location_id.manage_expirydate', readonly=1)
    # Group type qty / value
    ice_cream_qty = fields.Float(string="Ice Cream Qty", digits=(18, 2), compute='_get_group_type_data')
    ice_cream_value = fields.Float(string="Ice Cream Value", digits=(18, 2), compute='_get_group_type_data')
    packaging_qty = fields.Float(string="Packaging Qty", digits=(18, 2), compute='_get_group_type_data')
    packaging_value = fields.Float(string="Packaging Value", digits=(18, 2), compute='_get_group_type_data')
    cake_qty = fields.Float(string="Cake Qty", digits=(18, 2), compute='_get_group_type_data')
    cake_value = fields.Float(string="Cake value", digits=(18, 2), compute='_get_group_type_data')
    others_qty = fields.Float(string="Others Qty", digits=(18, 2), compute='_get_group_type_data')
    others_value = fields.Float(string="Others Value", digits=(18, 2), compute='_get_group_type_data')
    last_inventory_date = fields.Datetime(string="Last Date", store=True, compute='_get_last_inventory_date',
                                          help="The inventory date of the latest official stockcount of that inventoried location")
    inventory_action_id = fields.Many2one(comodel_name="stock.inventory.action", string="Action", ondelete='restrict')

    @api.multi
    def action_refresh_summary(self):
        for record in self:
            record._get_summary_lines()

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        if self.warehouse_id:
            view_loc = self.warehouse_id.view_location_id.id
            stock_location = self.env["stock.location"].search([('id', 'child_of', view_loc), ('is_stock_location', '=', True)])
            if stock_location:
                self.location_id = stock_location
        else:
            self.location_id = False

    @api.onchange('stock_count_type')
    def onchange_stock_count_type(self):
        if self.stock_count_type and self.stock_count_type == 'official':
            self.manage_expirydate = True

    @api.depends('location_id')
    @api.multi
    def _get_last_inventory_date(self):
        """
        Get inventory date of last official count by locations
        """
        location_ids = self.mapped('location_id').ids
        if location_ids:
            self.env.cr.execute("""
                SELECT
                  location_id,
                  max(date) as last_inventory_date
                FROM stock_inventory
                WHERE stock_count_type = 'official'
                  AND location_id IN %s
                GROUP BY date, location_id""", (tuple(location_ids), ))
            inventory_date = {x['location_id']: x['last_inventory_date'] for x in self.env.cr.dictfetchall()}
            for inventory in self:
                if inventory.location_id and inventory.location_id.id in inventory_date:
                    inventory.last_inventory_date = inventory_date[inventory.location_id.id]

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == '/' or not vals['name']:
            vals['name'] = self.generate_inventory_name(vals['location_id'], vals['template_id'],
                                                        vals['accounting_date'])
        return super(StockInventory, self).create(vals)

    @api.multi
    def write(self, vals):
        if 'location_id' in vals or 'template_id' in vals or 'accounting_date' in vals:
            sequence = self.name.split("-")[-1][6:]  # last part is date (yymmdd) + sequence
            location_id = self.location_id.id if 'location_id' not in vals else vals['location_id']
            template_id = self.template_id.id if 'template_id' not in vals else vals['template_id']
            accounting_date = self.accounting_date if 'accounting_date' not in vals else vals['accounting_date']
            vals['name'] = self.generate_inventory_name(location_id, template_id, accounting_date, sequence)
        return super(StockInventory, self).write(vals)

    def generate_inventory_name(self, location_id, template_id, accounting_date, sequence=None):
        location_obj = self.env['stock.location']
        location = location_obj.browse(location_id)
        warehouse = self.env['stock.warehouse'].browse(location_obj.get_warehouse(location))
        template = self.env['stock.inventory.template'].browse(template_id)
        sequence = sequence or self.env.ref('br_inventory_adjustment.inventory_adjustment_sequence').next_by_id()
        accounting_date = datetime.strptime(accounting_date, '%Y-%m-%d').strftime("%y%m%d")
        return "%s-%s-%s%s" % (warehouse.name, template.name, accounting_date, sequence)

    @api.multi
    def action_to_first_degree(self):
        return self.set_action_case('1st_degree')

    @api.multi
    def action_to_second_degree(self):
        return self.set_action_case('2nd_degree')

    @api.multi
    def action_to_no_case(self):
        return self.set_action_case('no_case')

    @api.multi
    def action_confirm(self):
        # validate official
        self.validate_data(self.line_ids)
        # validate unofficial
        self.validate_data(self.line_unofficial_ids)

        if self.state == 'official_acount_initiated':
            self.write({'state': 'official_count_in_progress'})
        else:
            super(StockInventory, self).action_confirm()
        self._get_summary_lines()

    def validate_data(self, lines):
        for line in lines:
            if line.product_qty < 0:
                raise UserError(_('You cannot set a negative product quantity in an '
                                  'inventory line:\n\t%s - qty: %s') % (line.product_id.name, line.product_qty))


    def set_action_case(self, case):
        ir_model_data = self.env['ir.model.data']
        view_id = ir_model_data.get_object_reference('br_inventory_adjustment', 'inventory_set_action_form')[1]
        ctx = self.env.context.copy()
        ctx['inventory_ids'] = self.ids
        ctx['inventory_case'] = case

        return {
            'name': 'Set Inventory Action',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.inventory.set.action',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def _get_group_type_data(self):
        for inventory in self:
            data = inventory._get_line_grouped_by_type()
            for type, _ in GROUP_TYPE:
                if type in data:
                    setattr(inventory, '%s_%s' % (type, 'qty'), data[type]['qty'])
                    setattr(inventory, '%s_%s' % (type, 'value'), data[type]['amount'])
                else:
                    setattr(inventory, '%s_%s' % (type, 'qty'), 0)
                    setattr(inventory, '%s_%s' % (type, 'value'), 0)

    @api.constrains('name')
    def check_name_unique(self):
        if self.template_id:
            res = self.search([('id', '!=', self.id), ('name', '=', self.name)])
            if res:
                raise ValidationError("The name of the Inventory Adjustment must be unique!")

    @api.model
    def default_get(self, fields):
        rec = super(StockInventory, self).default_get(fields)
        now = datetime.now() + timedelta(hours=8)
        rec['accounting_date'] = now.strftime(DEFAULT_SERVER_DATE_FORMAT)
        return rec

    @api.multi
    def _get_summary_total(self):
        for inventory in self:
            inventory.summary_total = sum([x.amount for x in inventory.summary_line_ids])

    @api.onchange('template_id', 'accounting_date')
    def onchange_template_id(self):
        if self.template_id:
            self.filter = self.template_id.filter

    def post_inventory(self, inventory):
        res = super(StockInventory, self).post_inventory(inventory)
        self._get_summary_lines()
        return res

    @api.multi
    def _get_summary_lines(self):
        lines = self._prepare_summary_lines()
        self.summary_line_ids.unlink()
        summary_lines = self.env['stock.inventory.summary']
        for l in lines:
            summary_lines |= self.env['stock.inventory.summary'].create(lines[l])
        self.summary_line_ids = summary_lines

    @api.multi
    def _prepare_summary_lines(self):
        """ Group official / unofficial inventory line by template line's group name """
        group_by_names = {}
        grouped_lines = self.get_lines_grouped(filter_stockable_consumable=True)
        for group_type, line in grouped_lines.items():
            for k, v in line.items():
                if k not in group_by_names:
                    group_by_names[k] = v
                else:
                    group_by_names[k]['amount'] += v['amount']
                    group_by_names[k]['qty'] += v['qty']
        return group_by_names

    def _get_line_grouped_by_type(self):
        """
        Group official / unofficial inventory line by template line's group type
        :return:
        """
        group_by_type = {}
        grouped_lines = self.get_lines_grouped()
        for group_type, line in grouped_lines.items():
            if group_type == False:
                # Line without template's line is considered as 'others' group
                group_type = 'others'
            for k, v in line.items():
                if group_type not in group_by_type:
                    group_by_type[group_type] = v
                else:
                    group_by_type[group_type]['amount'] += v['official_amount'] or v['amount']
                    group_by_type[group_type]['qty'] += v['official_qty'] or v['qty']
        return group_by_type

    def get_lines_grouped(self, filter_stockable_consumable=False):
        """
        Get all official / unoffical inventory line then group them by group type and group name
        :return:
        """
        inventory_id = self.id
        line_grouped = {}
        # Prefer getting summary from moves
        # lines = self.move_ids or self.line_ids if self.stock_count_type == 'official' else self.line_unofficial_ids
        uom_obj = self.env['product.uom']
        for line in self.line_unofficial_ids:
            qty = orig_qty = line.product_qty - line.theoretical_qty
            if line.template_line_id.is_total_count:
                # If count by total then sum all product's price (converted to template's uom)
                # then divide by total product to get price
                all_products = line.template_line_id.all_product_ids
                uom_type = line.template_line_id.uom_type
                price_total = sum(
                    [uom_obj._compute_qty_obj(x._get_uom_by_type(uom_type or 'standard'), x.standard_price, x.uom_id)
                     for x in all_products])
                product_length = len(all_products)
                price = price_total / product_length if product_length else 0
                # Convert qty to loss/gain uom using reference product on template
                ref_product = line.template_line_id.ref_product_id
                loss_gain_uom = ref_product._get_uom_by_type(line.template_line_id.uom_type or 'standard')
                qty = uom_obj._compute_qty_obj(ref_product.uom_id, qty, loss_gain_uom)
            else:
                price = line.product_id.standard_price
                loss_gain_uom = line.product_id._get_uom_by_type(line.template_line_id.uom_type or 'standard')
                if line.product_id.uom_id != loss_gain_uom:
                    # Convert product's qty to template uom
                    qty = uom_obj._compute_qty_obj(line.product_id.uom_id, orig_qty, loss_gain_uom)
            line_grouped.setdefault(line.group_type, {})
            if line.group_name not in line_grouped[line.group_type]:
                line_grouped[line.group_type][line.group_name] = {
                    'inventory_id': inventory_id,
                    'group_name': line.group_name if line.group_name else "Others",
                    'uom_type': line.template_line_id.uom_type if line.template_line_id else 'standard',
                    'amount': qty * price,
                    'qty': qty,
                    'official_qty': 0,
                    'official_amount': 0
                }
            else:
                line_grouped[line.group_type][line.group_name]['amount'] += qty * price
                line_grouped[line.group_type][line.group_name]['qty'] += qty

        # Official count summary, if moves are created get summary from moves instead of inventory line
        lines = self.move_ids or self.line_ids
        for line in lines:
            if line._name == 'stock.move':
                price = line.quant_ids[0].cost if line.quant_ids else line.product_id.standard_price
                line = line.inventory_line_id
                if not line:
                    break
            else:
                price = line.product_id.standard_price
            qty = line.product_qty - line.theoretical_qty
            loss_gain_uom = line.product_id._get_uom_by_type(line.template_line_id.uom_type or 'standard')
            temp_qty = uom_obj._compute_qty_obj(line.product_id.uom_id, qty, loss_gain_uom)
            line_grouped.setdefault(line.group_type, {})
            if not filter_stockable_consumable or (filter_stockable_consumable and not line.product_id.categ_id.is_stockable_consumable):
                if line.group_name not in line_grouped[line.group_type]:
                    line_grouped[line.group_type][line.group_name] = {
                        'inventory_id': inventory_id,
                        'group_name': line.group_name if line.group_name else "Others",
                        'uom_type': line.template_line_id.uom_type if line.template_line_id else 'standard',
                        'official_amount': qty * price,
                        'official_qty': temp_qty,
                        'qty': 0,
                        'amount': 0
                    }
                else:
                    line_grouped[line.group_type][line.group_name]['official_amount'] += qty * price
                    line_grouped[line.group_type][line.group_name]['official_qty'] += temp_qty

        return line_grouped

    @api.onchange('warehouse_id', 'stock_count_type')
    def onchange_warehouse_id(self):
        """Force re-Select template"""
        self.template_id = False
        if self.stock_count_type == 'official':
            self.manage_expirydate = True

    @api.multi
    def prepare_inventory(self):
        new_ctx = self.env.context.copy()
        new_ctx.update(lines_checked=True)
        for inventory in self.with_context(new_ctx):
            if inventory.state in ('draft', 'waiting') and inventory.stock_count_type == 'official':
                outlet = self.env['br_multi_outlet.outlet'].search([('warehouse_id', '=', inventory.warehouse_id.id)])
                session = self.env['pos.session'].search([('outlet_id', '=', outlet.id),
                                                          ('state', 'not in', ['opening_control', 'closed'])])
                if session:
                    raise UserError(_("POS session is still open. Please close and post session before starting inventory adjustment."))
            if inventory.state == 'waiting':
                raise UserError(_("You can not start inventory : %s which is already started !") % (inventory.name))
            line_obj = self.with_context(new_ctx).env['stock.inventory.line' if inventory.stock_count_type == 'official' else 'stock.inventory.line.unofficial']
            if inventory.filter == 'none':
                if inventory.stock_count_type == 'official':
                    # If stock count is official, do normal inventory adjustment
                    super(StockInventory, inventory).prepare_inventory()
                elif inventory.stock_count_type == 'unofficial':
                    for inventory_lines in self._get_inventory_lines(inventory):
                        inventory_lines.update(product_qty=0)
                        line = line_obj.create(inventory_lines)
                        line.is_edit_lot = self.get_is_edit_lot(line)
            elif inventory.filter == 'partial':
                template_inventory_lines = inventory._get_template_inventory_lines()
                for inventory_lines in template_inventory_lines:
                    line = line_obj.create(inventory_lines)
                    line.is_edit_lot = self.get_is_edit_lot(line)
        self.write({'state': 'waiting', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

    @api.model
    def get_is_edit_lot(self, line):
        is_edit_lot = False
        if self.location_id.manage_expirydate and self.manage_expirydate:
            if not line.prod_lot_id and line.product_id.tracking in ['serial', 'lot'] and line.theoretical_qty == 0:
                is_edit_lot = True
        return is_edit_lot

    @api.model
    def check_valid_inventory_lines(self, lines):
        """
        Odoo always checks for "in process" inventory line whenever create a new inventory line
        which will be very slow when start inventory with large number of lines,
        so change to check by batch instead of line by line
        """
        if lines:
            doms = []
            criterias = ['product_id', 'location_id', 'partner_id', 'prod_lot_id', 'br_supplier_id']
            for l in lines:
                dom = []
                for c in criterias:
                    dom.append(
                        'stock_inventory_line.%s = %s' % (c, l[c]) if c in l and l[c] else 'stock_inventory_line.%s is NULL' % c
                    )
                doms.append(dom)
            where = " OR ".join(["(" + " AND ".join(x) + ")" for x in doms])
            query = """
            SELECT stock_inventory_line.product_id, stock_inventory_line.location_id
            FROM stock_inventory_line
            INNER JOIN stock_inventory ON stock_inventory_line.inventory_id = stock_inventory.id
            WHERE stock_inventory.state = 'waiting'
            AND (%s)
            """ % where
            self.env.cr.execute(query)
            r = self.env.cr.dictfetchall()
            if r:
                location = self.env['stock.location'].browse(r[0]['location_id'])
                product = self.env['product.product'].browse(r[0]['product_id'])
                raise UserError(_(
                    "You cannot have two inventory adjustements in state 'in Progess' with the same product(%s), same location(%s), same package, same owner and same lot. Please first validate the first inventory adjustement with this product before creating another one.") % (
                                    product.name, location.complete_name))

    def _get_inventory_lines(self, cr, uid, inventory, context=None):
        """Group inventory line, if line's product isn't set in template then push that line to 'Others' group"""
        inventory_lines = super(StockInventory, self)._get_inventory_lines(cr, uid, inventory, context=context)
        res = []
        # Get all product in template
        template = inventory.template_id
        template_products = {}
        for tmpline in template.line_ids:
            for product in tmpline.all_product_ids:
                template_products[product.id] = tmpline
        traveled_lines = []
        for l in inventory_lines:
            # Check if product is in inventory lines or not, if yes then update line's information
            # otherwise, add it to group "Others"
            if l['product_id'] in template_products:
                # Get template line from product
                template_line = template_products[l['product_id']]
                l['template_line_id'] = template_line.id
                l['group_name'] = template_line.group_name
                # If template line is total count which
                if template_line.is_total_count and inventory.stock_count_type == 'unofficial':
                    if template_line.id not in traveled_lines:
                        ref_product = template_line.ref_product_id
                        supplier = ref_product.product_tmpl_id.get_default_supplier()
                        l.update(product_qty=0,
                                 product_id=ref_product.id,
                                 br_supplier_id=supplier.name.id if supplier else False,
                                 product_uom_id=ref_product.uom_id.id,
                                 partner_id=False,
                                 prod_lot_id=False,
                                 )
                        res.append(l)
                        traveled_lines.append(template_line.id)
                else:
                    res.append(l)
            else:
                l['template_line_id'] = False
                l['group_name'] = "Others"
                res.append(l)
        self.check_valid_inventory_lines(cr, uid, res, context=context)
        return res

    @api.multi
    def action_cancel_draft(self):
        self.write({'line_unofficial_ids': [(5,)], 'is_from_unofficial': False})
        return super(StockInventory, self).action_cancel_draft()

    @api.multi
    def action_to_official(self):
        self.ensure_one()
        self.write({'stock_count_type': 'official', 'is_from_unofficial': True})
        inventory_lines = []
        for line in self.line_unofficial_ids:
            inventory_lines.extend(self._get_official_line(line))
        vals = {'line_ids': inventory_lines}
        if self.state == 'done':
            vals.update(state='official_acount_initiated')
        self.write(vals)
        return True

    @api.multi
    def _get_official_line(self, line):
        if not line.is_total_count:
            return [(0, 0, {
                'group_name': line.group_name,
                'inventory_id': line.inventory_id.id,
                'is_loaded': line.is_loaded,
                'product_id': line.product_id.id,
                'location_id': line.location_id.id if line.location_id else None,
                'br_supplier_id': line.br_supplier_id.id if line.br_supplier_id else None,
                'account_analytic_id': line.account_analytic_id.id if line.account_analytic_id else None,
                'prod_lot_id': line.prod_lot_id.id if line.prod_lot_id else None,
                'br_qty_l1': line.br_qty_l1,
                'product_standard_uom': line.product_standard_uom.id if line.product_standard_uom else None,
                'product_uom_id': line.product_uom_id.id if line.product_uom_id else None,
                'br_qty_l2': line.br_qty_l2,
                'br_uom_l2': line.br_uom_l2.id if line.br_uom_l2 else None,
                'br_qty_l3': line.br_qty_l3,
                'br_uom_l3': line.br_uom_l3.id if line.br_uom_l3 else None,
                'br_qty_l4': line.br_qty_l4,
                'br_uom_l4': line.br_uom_l4.id if line.br_uom_l3 else None,
                'package_id': line.package_id.id if line.package_id else None,
                'partner_id': line.partner_id.id if line.partner_id else None,
                'product_qty': line.product_qty,
                'state': line.state,
                'remark': line.remark
            })]
        else:
            return [(0, 0, val) for val in self._get_template_inventory_lines(line)]

    def get_product_supplier(self, product):
        supplier = product.product_tmpl_id.get_default_supplier()
        if not supplier:
            sellers = product.product_tmpl_id.seller_ids
            supplier = sellers[0] if len(sellers) == 1 else False
        return supplier

    def set_uom_level(self, line_value, supplier):
        if supplier:
            supplier_uoms = supplier.get_uom_by_levels()
            line_value.update(
                br_uom_l2=supplier_uoms['level2'].id if 'level2' in supplier_uoms else False,
                br_uom_l3=supplier_uoms['level3'].id if 'level3' in supplier_uoms else False,
                br_uom_l4=supplier_uoms['level4'].id if 'level4' in supplier_uoms else False,
            )

    @api.multi
    def _get_template_inventory_lines(self, unofficial_line=None):
        self.ensure_one()
        vals = []
        product_obj = self.env['product.product']
        template_products = {}
        inventory_products = []
        if unofficial_line and unofficial_line.template_line_id:
            for product in unofficial_line.template_line_id.all_product_ids:
                template_products[product.id] = unofficial_line.template_line_id
        else:
            for line in self.template_id.line_ids:
                for product in line.all_product_ids:
                    template_products[product.id] = line
        if template_products:
            domain = ' product_id in %s'
            args = (tuple(template_products),)
            if self.location_id:
                location_obj = self.env['stock.location']
                location_ids = location_obj.search([('id', 'child_of', [self.location_id.id])])
                domain += ' and location_id in %s'
                args += (tuple(location_ids.ids),)
            if self.company_id:
                domain += ' and company_id = %s'
                args += (self.company_id.id,)
            self.env.cr.execute(self._get_inventory_lines_query(domain, self), args)
            lines_data = self.env.cr.dictfetchall()
            group_items = {}
            stock_count_type = self.stock_count_type
            for product_line in lines_data:
                # replace the None the dictionary by False, because falsy values are tested later on
                for key, value in product_line.items():
                    if not value:
                        product_line[key] = False
                temp_line = template_products[product_line['product_id']]
                product_line['is_loaded'] = True
                product_line['group_name'] = temp_line.group_name
                product_line['template_line_id'] = temp_line.id
                product_line['inventory_id'] = self.id
                product_line.update(product_qty=0)
                if product_line['product_id']:
                    product = self.env['product.product'].browse(product_line['product_id'])
                    product_line['product_uom_id'] = product.uom_id.id
                    inventory_products.append(product.id)
                # Group product_line by group name
                if not temp_line.is_total_count or stock_count_type == 'official':
                    inv_product = product_obj.browse(product_line['product_id'])
                    if 'br_supplier_id' in product_line and product_line['br_supplier_id']:
                        supplier = inv_product.product_tmpl_id.seller_ids.filtered(lambda x: x.name.id == product_line['br_supplier_id'])
                        supplier = supplier[0] if supplier else False
                    else:
                        supplier = self.get_product_supplier(inv_product)
                    self.set_uom_level(product_line, supplier)
                    vals.append(product_line)
                else:
                    if temp_line.group_name not in group_items:
                        ref_product = temp_line.ref_product_id
                        if ref_product:
                            supplier = self.get_product_supplier(ref_product)
                            self.set_uom_level(product_line, supplier)
                            product_line.update(
                                product_id=ref_product.id,
                                br_supplier_id=supplier.name.id if supplier else False,
                                product_uom_id=ref_product.uom_id.id,
                                partner_id=False,
                                prod_lot_id=False,
                            )
                        group_items[temp_line.group_name] = product_line
            # Products that can't be found in location but configured on template
            remaining_products = self.env['product.product'].browse(
                [x for x in template_products if x not in inventory_products])
            for product in remaining_products:
                temp_line = template_products[product.id]
                # If inventory line is total count or this is official inventory then don't need to fill in product info
                if not temp_line.is_total_count or stock_count_type == 'official':
                    supplier = self.get_product_supplier(product)
                    product_line = {
                        'is_loaded': True,
                        'group_name': temp_line.group_name,
                        'template_line_id': temp_line.id,
                        'inventory_id': self.id,
                        'theoretical_qty': 0,
                        'prod_lot_id': False,
                        'package_id': False,
                        'partner_id': False,
                        'br_supplier_id': supplier.name.id if supplier else False,
                        'product_id': product.id,
                        'product_uom_id': product.uom_id.id,
                        'location_id': self.location_id.id
                    }
                    self.set_uom_level(product_line, supplier)
                    vals.append(product_line)
                else:
                    if temp_line.group_name not in group_items:
                        group_items[temp_line.group_name] = {
                            # 'is_loaded': True,
                            'group_name': temp_line.group_name,
                            'template_line_id': temp_line.id,
                            'inventory_id': self.id,
                            'theoretical_qty': 0,
                            'prod_lot_id': False,
                            'package_id': False,
                            'partner_id': False,
                            'location_id': self.location_id.id,
                        }
                        ref_product = temp_line.ref_product_id
                        if ref_product:
                            supplier = self.get_product_supplier(ref_product)
                            self.set_uom_level(group_items[temp_line.group_name], supplier)
                            group_items[temp_line.group_name].update(
                                product_id=ref_product.id,
                                br_supplier_id=supplier.name.id if supplier else False,
                                product_uom_id=ref_product.uom_id.id,
                                partner_id=False,
                                prod_lot_id=False,
                            )
            vals.extend([group_items[x] for x in group_items])
        self.check_valid_inventory_lines(vals)
        return vals

    def _get_inventory_lines_query(self, domain, inventory):
        sql = '''
            SELECT
             product_id, sum(qty) as product_qty,
             location_id,
             {lot_select}
             vendor_id as br_supplier_id,
             package_id,
             owner_id as partner_id
            FROM stock_quant
            WHERE''' + domain + '''
            GROUP BY product_id, location_id, {lot_group}vendor_id, package_id, partner_id
         '''
        if inventory.location_id.manage_expirydate and inventory.manage_expirydate:
            sql = sql.format(
                lot_select='lot_id as prod_lot_id,', lot_group='lot_id, '
            )
        else:
            sql = sql.format(
                lot_select='FALSE as prod_lot_id,', lot_group='',
            )
        return sql

class StockInventoryLine(models.Model):
    _inherit = 'stock.inventory.line'
    _order = 'is_total_count DESC, group_name, product_name, br_supplier_id, prod_lot_id'

    template_line_id = fields.Many2one(comodel_name='stock.inventory.template.line', string="Template Line", ondelete='restrict')
    group_name = fields.Char(string="Template Group Name")
    group_type = fields.Selection(selection=GROUP_TYPE, string="Template Group Type",
                                  related='template_line_id.group_type')
    is_total_count = fields.Boolean(related='template_line_id.is_total_count', store=True)

    @api.model
    def create(self, vals):
        # add group name according to template
        if 'product_id' in vals and 'inventory_id' in vals:
            inventory = self.env['stock.inventory'].search([
                ('id', '=', vals['inventory_id'])])
            template = inventory.template_id
            template_products = {}
            if template:
                for tmpline in template.line_ids:
                    for product in tmpline.all_product_ids:
                        template_products[product.id] = tmpline
            if vals['product_id'] in template_products:
                template_line = template_products[vals['product_id']]
                vals['template_line_id'] = template_line.id
                vals['group_name'] = template_line.group_name
        return super(StockInventoryLine, self).create(vals)


    @api.onchange('product_id', 'br_supplier_id')
    def onchange_theoretical_qty(self):
        if self.product_id and self.br_supplier_id:
            line = self
            quant_ids = self._get_quants(line)
            quants = self.env['stock.quant'].search([('id', 'in', quant_ids)])
            tot_qty = sum([x.qty for x in quants])
            if self.product_uom_id and self.product_id.uom_id.id != self.product_uom_id.id:
                tot_qty = self.env['product.uom']._compute_qty_obj(
                    self.product_id.uom_id, tot_qty, self.product_uom_id)
            self.theoretical_qty = tot_qty

    def _get_quant_dom(self, line):
        dom = [('company_id', '=', line.company_id.id),
               ('location_id', '=', line.location_id.id),
               ('product_id', '=', line.product_id.id),
               ('owner_id', '=', line.partner_id.id),
               ('package_id', '=', line.package_id.id),
               ('vendor_id', '=', line.br_supplier_id.id if line.br_supplier_id else None)
               ]
        if line.location_id.manage_expirydate and line.inventory_id.manage_expirydate:
            dom.append(('lot_id', '=', line.prod_lot_id.id))
        return dom

    @api.multi
    def write(self, vals):
        # update group name when user edit the product
        if 'product_id' in vals:
            template = self.inventory_id.template_id
            template_products = {}
            if template:
                for tmpline in template.line_ids:
                    for product in tmpline.all_product_ids:
                        template_products[product.id] = tmpline
            if vals['product_id'] in template_products:
                template_line = template_products[vals['product_id']]
                self.template_line_id = template_line.id
                self.group_name = template_line.group_name
            else:
                self.template_line_id = False
                self.group_name = False
        res = super(StockInventoryLine, self).write(vals)
        list_product = ''
        for line in self:
            if line.inventory_id.location_id.manage_expirydate and line.inventory_id.manage_expirydate:
                if line.product_id.tracking in ['serial', 'lot'] and not line.prod_lot_id \
                        and line.product_qty > 0:
                    list_product += line.product_id.name + ', '
        if list_product:
            # remove the last ', '
            list_product = list_product[:len(list_product)-2]
            raise ValidationError(
                "Some products require Lot/Expiry Date: %s" % list_product)
        return res


class StockInventorySummary(models.Model):
    _name = 'stock.inventory.summary'

    inventory_id = fields.Many2one(comodel_name='stock.inventory', string="Inventory")
    group_name = fields.Char(string="Group Name")
    uom_type = fields.Selection(string="UOM Type", selection=UOM_TYPE)
    qty = fields.Float(string="Unofficial Loss/Gain Qty", digits=(18, 2))
    amount = fields.Float(string="Unofficial Loss/Gain Amount", digits=(18, 2))
    official_qty = fields.Float(string="Official Loss/Gain Qty", digits=(18, 2))
    official_amount = fields.Float(string="Official Loss/Gain Amount", digits=(18, 2))
    stock_count_type = fields.Selection(selection=STOCK_COUNT_TYPE, string="Template Type",
                                        related='inventory_id.stock_count_type')
    is_from_unofficial = fields.Boolean(related='inventory_id.is_from_unofficial')


class StockInventoryLineUnofficial(models.Model):
    _name = 'stock.inventory.line.unofficial'
    _order = 'is_total_count DESC, group_name, product_name, br_supplier_id, prod_lot_id'
    _inherit = 'stock.inventory.line'

    def _get_product_name_change(self, cr, uid, ids, context=None):
        return self.pool.get('stock.inventory.line.unofficial').search(cr, uid, [('product_id', 'in', ids)],
                                                                       context=context)

    def _get_location_change(self, cr, uid, ids, context=None):
        return self.pool.get('stock.inventory.line.unofficial').search(cr, uid, [('location_id', 'in', ids)],
                                                                       context=context)

    def _get_prodlot_change(self, cr, uid, ids, context=None):
        return self.pool.get('stock.inventory.line.unofficial').search(cr, uid, [('prod_lot_id', 'in', ids)],
                                                                       context=context)

    def _get_theoretical_qty(self, cr, uid, ids, name, args, context=None):
        res = {}
        quant_obj = self.pool["stock.quant"]
        uom_obj = self.pool["product.uom"]
        for line in self.browse(cr, uid, ids, context=context):
            quant_ids = self._get_quants(cr, uid, line, context=context)
            quants = quant_obj.browse(cr, uid, quant_ids, context=context)
            tot_qty = sum([x.qty for x in quants])
            if line.product_uom_id and line.product_id.uom_id.id != line.product_uom_id.id:
                tot_qty = uom_obj._compute_qty_obj(cr, uid, line.product_id.uom_id, tot_qty, line.product_uom_id,
                                                   context=context)
            res[line.id] = tot_qty
        return res

    def _get_quant_dom(self, line):
        if line.template_line_id.is_total_count and line.inventory_id.stock_count_type == 'unofficial':
            dom = [
                ('company_id', '=', line.company_id.id),
                ('location_id', '=', line.location_id.id),
                ('product_id', 'in', line.template_line_id.all_product_ids.ids)
            ]
        else:
            dom = super(StockInventoryLineUnofficial, self)._get_quant_dom(line)
        return dom

    @api.model
    def create(self, vals):
        # NOTE: Override entirely create function because we don't want any surprise from parent model

        """ create(vals) -> record

            Creates a new record for the model.

            The new record is initialized using the values from ``vals`` and
            if necessary those from :meth:`~.default_get`.

            :param dict vals:
                values for the model's fields, as a dictionary::

                    {'field_name': field_value, ...}

                see :meth:`~.write` for details
            :return: new record created
            :raise AccessError: * if user has no create rights on the requested object
                                * if user tries to bypass access rules for create on the requested object
            :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
            :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)
            """
        self.check_access_rights('create')

        # add missing defaults, and drop fields that may not be set by user
        vals = self._add_missing_default_values(vals)
        for field in itertools.chain(MAGIC_COLUMNS, ('parent_left', 'parent_right')):
            vals.pop(field, None)

        # split up fields into old-style and pure new-style ones
        old_vals, new_vals, unknown = {}, {}, []
        for key, val in vals.iteritems():
            field = self._fields.get(key)
            if field:
                if field.column or field.inherited:
                    old_vals[key] = val
                if field.inverse and not field.inherited:
                    new_vals[key] = val
            else:
                unknown.append(key)

        if unknown:
            _logger.warning("%s.create() includes unknown fields: %s", self._name, ', '.join(sorted(unknown)))

        # create record with old-style fields
        record = self.browse(self._create(old_vals))

        # put the values of pure new-style fields into cache
        record._cache.update(record._convert_to_cache(new_vals))
        # mark the fields as being computed, to avoid their invalidation
        for key in new_vals:
            self.env.computed[self._fields[key]].add(record.id)
        # inverse the fields
        for key in new_vals:
            self._fields[key].determine_inverse(record)
        for key in new_vals:
            self.env.computed[self._fields[key]].discard(record.id)

        return record

    _columns = {
        'product_id': Ofields.many2one('product.product', 'Product', select=True),
        'theoretical_qty': Ofields.function(_get_theoretical_qty, type='float',
                                            digits_compute=dp.get_precision('Product Unit of Measure'),
                                            store={'stock.inventory.line.unofficial': (
                                                lambda self, cr, uid, ids, c={}: ids,
                                                ['location_id', 'product_id', 'package_id', 'product_uom_id',
                                                 'company_id',
                                                 'prod_lot_id', 'partner_id'], 20), },
                                            readonly=True, string="Theoretical Quantity"),
        'product_name': Ofields.related('product_id', 'name', type='char', string='Product Name', store={
            'product.product': (_get_product_name_change, ['name', 'default_code'], 20),
            'stock.inventory.line.unofficial': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 20), }),
        'product_code': Ofields.related('product_id', 'default_code', type='char', string='Product Code', store={
            'product.product': (_get_product_name_change, ['name', 'default_code'], 20),
            'stock.inventory.line.unofficial': (lambda self, cr, uid, ids, c={}: ids, ['product_id'], 20), }),
        'location_name': Ofields.related('location_id', 'complete_name', type='char', string='Location Name', store={
            'stock.location': (_get_location_change, ['name', 'location_id', 'active'], 20),
            'stock.inventory.line.unofficial': (lambda self, cr, uid, ids, c={}: ids, ['location_id'], 20), }),
        'prodlot_name': Ofields.related('prod_lot_id', 'name', type='char', string='Expiry Date', store={
            'stock.production.lot': (_get_prodlot_change, ['name'], 20),
            'stock.inventory.line.unofficial': (lambda self, cr, uid, ids, c={}: ids, ['prod_lot_id'], 20), }),
        'product_uom_id': Ofields.many2one('product.uom', 'Product Unit of Measure', required=False),
    }

    _defaults = {
        'product_uom_id': False,
    }


class StockInventoryAction(models.Model):
    _name = 'stock.inventory.action'

    name = fields.Char(string="Action", required=1)
    active = fields.Boolean(string="Active", default=True)

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        if self._context.get('adjustment_warehouse_filter'):
            domain += [('id', 'in', self.env.user.warehouse_ids.ids)]
        return super(StockWarehouse, self).name_search(
            name, args=domain + args, operator=operator, limit=limit)