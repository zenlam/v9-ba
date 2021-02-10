from openerp.osv import osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp import tools
from openerp.exceptions import UserError, AccessError

class stock_change_product_qty(osv.osv_memory):
    _inherit = 'stock.change.product.qty'

    def _prepare_inventory_line(self, cr, uid, inventory_id, data, context=None):
        context = context or {}
        res = super(stock_change_product_qty, self)._prepare_inventory_line(cr, uid, inventory_id, data, context=context)
        analytic_account_id = self.get_analytic_account(cr, uid, inventory_id, data, context)
        res.update(account_analytic_id=analytic_account_id and analytic_account_id.id or None)
        return res

    def get_analytic_account(self, cr, uid, ids, data, context):
        analytic_account_id = data.location_id.br_analytic_account_id
        if not analytic_account_id:
            outlet = data.location_id.get_outlet()
            if outlet:
                analytic_account_id = outlet.analytic_account_id
        return analytic_account_id

    def _prepare_inventory(self, cr, uid, ids, data, filter, context):
        loss_location = data.location_id.get_loss_location()
        analytic_account_id = self.get_analytic_account(cr, uid, ids, data, context=context)
        return {
            'name': _('INV: %s') % tools.ustr(data.product_id.name),
            'filter': filter or 'none',
            'product_id': data.product_id.id,
            'location_id': data.location_id.id,
            'lot_id': data.lot_id.id,
            'br_loss_inventory_id': loss_location and loss_location[0].id or False,
            'account_analytic_id': analytic_account_id and analytic_account_id.id or False
        }

    def change_product_qty(self, cr, uid, ids, context=None):
        """ Changes the Product Quantity by making a Physical Inventory. """
        if context is None:
            context = {}

        inventory_obj = self.pool.get('stock.inventory')
        inventory_line_obj = self.pool.get('stock.inventory.line')

        for data in self.browse(cr, uid, ids, context=context):
            if data.new_quantity < 0:
                raise UserError(_('Quantity cannot be negative.'))
            ctx = context.copy()
            ctx['location'] = data.location_id.id
            ctx['lot_id'] = data.lot_id.id
            if data.product_id.id and data.lot_id.id:
                filter = 'none'
            elif data.product_id.id:
                filter = 'product'
            else:
                filter = 'none'
            inventory_data = self._prepare_inventory(cr, uid, ids, data, filter, context)
            inventory_id = inventory_obj.create(cr, uid, inventory_data, context=context)

            line_data = self._prepare_inventory_line(cr, uid, inventory_id, data, context=context)

            inventory_line_obj.create(cr, uid, line_data, context=context)
            inventory_obj.action_done(cr, uid, [inventory_id], context=context)
        return {}

    def onchange_location_id(self, cr, uid, ids, location_id, product_id, context=None):
        context = context or {}
        _context = context.copy()
        _context.update(compute_child=False)
        res = super(stock_change_product_qty, self).onchange_location_id(cr, uid, ids, location_id, product_id, context=context)
        return res