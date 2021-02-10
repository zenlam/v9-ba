from openerp import models, api, _


class PosSession(models.Model):
    _inherit = 'pos.session'

    # @api.model
    # def prepare_domain_stock_transfers(self, start_date, end_date, pos_session):
    #     return [
    #         '&', '&', ('picking_type_code', 'in', ['incoming']),
    #         ('location_dest_id', '=', pos_session.outlet_id.warehouse_id.lot_stock_id.id),
    #         '|', '&', ('min_date', '<', str(end_date)), ('state', 'in', ['transit']),
    #         '&', '&', ('min_date', '>=', str(start_date)), ('min_date', '<=', str(end_date)), ('state', '=', 'done')
    #     ]
