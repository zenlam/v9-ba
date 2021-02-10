# -*- coding: utf-8 -*-

from openerp import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # Note: comment this field as long already added same field as compute and non store which create issue,
    # so in this commit remove field from here and make that field as store true which added by long
    # warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    @api.model
    def create(self, vals):
        res = super(StockWarehouse, self).create(vals)
        locations = self.env['stock.location']
        locations += res.wh_input_stock_loc_id
        locations += res.wh_qc_stock_loc_id
        locations += res.wh_pack_stock_loc_id
        locations += res.wh_output_stock_loc_id
        locations += res.lot_stock_id
        locations.write({'warehouse_id': res.id})
        return res
