# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    wh_flush_stock_loc_id = fields.Many2one('stock.location', 'Flush Location')

    @api.multi
    def action_view_flush_locations(self):
        """
        This function returns an action that display all flush locations of
        a warehouse.
        """
        action = self.env.ref('stock.action_location_form')
        result = action.read()[0]

        flush_location_domain = [('warehouse_id', '=', self.id),
                                 ('is_flush_location', '=', True)]
        flush_locations = \
            self.env['stock.location'].search(flush_location_domain)

        result['domain'] = "[('id','in',[" + ','.join(
            map(str, flush_locations.ids)) + "])]"
        result['context'] = ""
        return result

    def _prepare_flush_location(self):
        """
        Return the flush location values
        """
        return {
            'warehouse_id': self.id,
            'location_id': self.view_location_id.id,
            'is_flush_location': True,
            'usage': 'inventory',
        }

