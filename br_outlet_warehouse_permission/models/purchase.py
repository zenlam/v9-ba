from openerp import fields, models, api, _
import br_model


class PurchasOrder(br_model.BrModel):
    _inherit = 'purchase.order'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'purchase.order':
            picking_type_ids = user.picking_type_ids.ids
            empty_warehouse_picking_types = self.env['stock.picking.type'].search([('warehouse_id', '=', False)])
            picking_type_ids.extend(empty_warehouse_picking_types.ids)
            domain.extend([
                ('picking_type_id', 'in', picking_type_ids)
            ])
        return domain
