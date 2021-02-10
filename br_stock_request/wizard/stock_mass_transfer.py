from openerp import fields, api, models, _


class StockMassTransfer(models.TransientModel):
    _name = 'stock.mass.transfer'

    picking_ids = fields.Many2many(string="Transfer", comodel_name='stock.picking')

    @api.multi
    def do_transfer(self):
        picking_ids = self.env.context.get('active_ids', False)
        if picking_ids:
            pickings = self.env['stock.picking'].browse(picking_ids)
            for picking in pickings:
                picking.do_transit()