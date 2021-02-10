from openerp import models, api, fields, _
from datetime import datetime
from openerp.exceptions import ValidationError

class StockLocationFlush(models.TransientModel):
    _name = 'stock.location.flush'

    @api.onchange('location_dest_id')
    def _onchange_location_dest_id(self):
        if self.location_dest_id.br_analytic_account_id:
            self.analytic_account_id = self.location_dest_id.br_analytic_account_id
        else:
            wh = self.env['stock.location'].get_warehouse(self.location_dest_id)
            if wh:
                outlet = self.env['br_multi_outlet.outlet'].search(([('warehouse_id', '=', wh)]))
                if outlet:
                    self.analytic_account_id = outlet[0].analytic_account_id.id

    location_dest_id = fields.Many2one(comodel_name='stock.location', string='Destination Location')
    picking_type_id = fields.Many2one(comodel_name='stock.picking.type', string='Picking Type')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')

    @api.multi
    def action_confirm(self):
        location_id = self.env.context.get('location', False)
        location = self.env['stock.location'].browse(location_id)
        quant_domain = [
            ('qty', '>', 0),
            ('location_id', '=', location.id),
            ('reservation_id', '=', None)
        ]
        quants = self.env['stock.quant'].read_group(
            quant_domain,
            ['product_id', 'lot_id', 'qty'], ['product_id', 'lot_id'],
            lazy=False)
        if not quants:
            raise ValidationError(_("There is nothing in current location"))

        picking_vals = {
            'location_id': location.id,
            'location_dest_id': self.location_dest_id.id,
            'picking_type_id': self.picking_type_id.id,
            'date': datetime.now(),
            'origin': 'Flush ' + location.complete_name + '->' +
                      self.location_dest_id.complete_name
        }
        picking_id = self.env['stock.picking'].create(picking_vals)
        for quant in quants:
            product = self.env['product.product'].browse(
                quant['product_id'] and quant['product_id'][0] or False)
            move_dict = {
                'name': product.name or '',
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uos': product.uom_id.id,
                'product_uom_qty': quant['qty'],
                'date': datetime.now(),
                'date_expected': datetime.now(),
                'account_analytic_id': self.analytic_account_id.id,
                'location_id': location.id,
                'location_dest_id': self.location_dest_id.id,
                'move_dest_id': False,
                'state': 'draft',
                'company_id': self.env.user.company_id.id,
                'picking_type_id': self.picking_type_id.id,
                'procurement_id': False,
                'origin': picking_id.origin,
                'invoice_state': 'none',
                'picking_id': picking_id.id
            }
            if quant['lot_id']:
                move_dict['restrict_lot_id'] = quant['lot_id'][0]
            move_id = self.env['stock.move'].create(move_dict)
            move_id.action_confirm()
        picking_id.action_assign()
        picking_id.do_new_transfer()
