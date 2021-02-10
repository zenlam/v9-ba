from openerp import models, fields, api, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import time
from openerp import SUPERUSER_ID
from openerp.exceptions import UserError


class br_stock_inventory_line(models.Model):
    _inherit = 'stock.inventory.line'

    @api.depends('product_uom_id')
    @api.multi
    def _get_product_standard_uom(self):
        for l in self:
            l.product_standard_uom = l.product_id.uom_id if l.product_id else None

    br_supplier_id = fields.Many2one('res.partner', string="Supplier")
    br_loss_inventory_id = fields.Many2one('stock.location', string="Loss Location")

    br_qty_l1 = fields.Float(string="Qty")
    br_qty_l2 = fields.Float(string="Qty")
    br_qty_l3 = fields.Float(string="Qty")
    br_qty_l4 = fields.Float(string="Qty")

    br_uom_l2 = fields.Many2one('product.uom', string="UOM L2")
    br_uom_l3 = fields.Many2one('product.uom', string="UOM L3")
    br_uom_l4 = fields.Many2one('product.uom', string="UOM L4")

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')], track_visibility='always'
                                          )

    product_standard_uom = fields.Many2one('product.uom', compute='_get_product_standard_uom')

    def create(self, cr, uid, values, context=None):
        product_obj = self.pool.get('product.product')
        dom = [('product_id', '=', values.get('product_id')), ('inventory_id.state', '=', 'waiting'),
               ('location_id', '=', values.get('location_id')), ('partner_id', '=', values.get('partner_id')),
               ('package_id', '=', values.get('package_id')), ('prod_lot_id', '=', values.get('prod_lot_id'))]
        res = self.search(cr, uid, dom, context=context)
        if res:
            location = self.pool['stock.location'].browse(cr, uid, values.get('location_id'), context=context)
            product = product_obj.browse(cr, uid, values.get('product_id'), context=context)
            raise UserError(_("You cannot have two inventory adjustements in state 'in Progess' with the same product(%s), same location(%s), same package, same owner and same lot. Please first validate the first inventory adjustement with this product before creating another one.") % (product.name, location.name))
        if 'product_id' in values and not 'product_uom_id' in values:
            values['product_uom_id'] = product_obj.browse(cr, uid, values.get('product_id'), context=context).uom_id.id
        return super(br_stock_inventory_line, self).create(cr, uid, values, context=context)

    @api.model
    def default_get(self, fields):
        rec = super(br_stock_inventory_line, self).default_get(fields)
        context = self._context
        # default analytic account id
        if 'default_analytic_account' in context and context['default_analytic_account']:
            rec['account_analytic_id'] = context['default_analytic_account']

        # default loss location id
        if 'default_loss_location' in context and context['default_loss_location']:
            rec['br_loss_inventory_id'] = context['default_loss_location']
        return rec

    @api.onchange('product_uom_id', 'br_qty_l1', 'br_qty_l2', 'br_qty_l3', 'br_qty_l4', 'br_uom_l2', 'br_uom_l3', 'br_uom_l4')
    def onchange_uom(self):
        uom_obj = self.env["product.uom"]
        prod_qty = 0
        if self.product_uom_id and self.br_qty_l1:
            prod_qty += uom_obj._compute_qty(self.product_uom_id.id, self.br_qty_l1, self.product_id.uom_id.id)
        if self.br_uom_l2 and self.br_qty_l2:
            prod_qty += uom_obj._compute_qty(self.br_uom_l2.id, self.br_qty_l2, self.product_id.uom_id.id)
        if self.br_uom_l3 and self.br_qty_l3:
            prod_qty += uom_obj._compute_qty(self.br_uom_l3.id, self.br_qty_l3, self.product_id.uom_id.id)
        if self.br_uom_l4 and self.br_qty_l4:
            prod_qty += uom_obj._compute_qty(self.br_uom_l4.id, self.br_qty_l4, self.product_id.uom_id.id)
        self.product_qty = prod_qty

    @api.onchange('prod_lot_id')
    def onchange_prod_lot_id(self):
        if self.prod_lot_id and self.product_id:
            self.br_supplier_id = self.prod_lot_id.br_supplier_id
            supplier = self.env['product.supplierinfo'].search([('name', '=', self.br_supplier_id.id)
                                                                   , ('product_tmpl_id', '=',
                                                                      self.product_id.product_tmpl_id.id)],
                                                               limit=1)
            if supplier:
                for item in supplier.uom_ids:
                    if item.level_uom == 'level2':
                        self.br_uom_l2 = item
                    if item.level_uom == 'level3':
                        self.br_uom_l3 = item
                    if item.level_uom == 'level4':
                        self.br_uom_l4 = item

                    self.product_uom_id = supplier.product_tmpl_id.uom_id

    @api.onchange('br_supplier_id')
    def onchange_supplier_id(self):
        if self.product_id and self.br_supplier_id:
            supplier = self.env['product.supplierinfo'].search([('name', '=', self.br_supplier_id.id)
                                                                   , ('product_tmpl_id', '=',
                                                                      self.product_id.product_tmpl_id.id)],
                                                               limit=1)
            if supplier:
                for item in supplier.uom_ids:
                    if item.level_uom == 'level2':
                        self.br_uom_l2 = item
                    if item.level_uom == 'level3':
                        self.br_uom_l3 = item
                    if item.level_uom == 'level4':
                        self.br_uom_l4 = item

                    self.product_uom_id = supplier.product_tmpl_id.uom_id

    def get_stock_move_vals(self, cr, uid, inventory_line, context=None):
        res = super(br_stock_inventory_line, self).get_stock_move_vals(cr, uid, inventory_line, context=context)
        res.update(account_analytic_id=inventory_line.account_analytic_id.id)
        return res

    def onchange_createline(self, cr, uid, ids, location_id=False, product_id=False, uom_id=False, package_id=False, prod_lot_id=False, partner_id=False, company_id=False, context=None):
        res = super(br_stock_inventory_line, self).onchange_createline(cr, uid, ids, location_id=location_id, product_id=product_id, uom_id=uom_id, package_id=package_id, prod_lot_id=prod_lot_id, partner_id=partner_id, company_id=company_id, context=context)
        if product_id:
            product = self.pool['product.product'].browse(cr, uid, product_id, context=context)
            uom = self.pool['product.uom'].browse(cr, uid, uom_id, context=context)
            if product.uom_id.category_id.id != uom.category_id.id:
                res['value']['product_uom_id'] = product.uom_id.id
        return res
