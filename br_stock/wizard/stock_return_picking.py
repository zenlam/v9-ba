from openerp import models, _
from openerp.exceptions import UserError


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _get_move_values(self, cr, uid, move, data_get, new_qty, new_picking, location_id, pick_type_id, pick, move_dest_id, data, context=None):
        res = super(StockReturnPicking, self)._get_move_values(cr, uid, move, data_get, new_qty, new_picking, location_id, pick_type_id, pick, move_dest_id, data, context=None)
        location_id = self.pool.get('stock.location').browse(cr, uid, location_id, context=context)
        if location_id:
            account_analytic_id = location_id.get_analytic_account()
            if account_analytic_id:
                res.update(account_analytic_id=account_analytic_id)
        return res

