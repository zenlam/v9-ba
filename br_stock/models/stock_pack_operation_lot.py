from openerp import models, api, fields, _


class StockPackOperationLot(models.Model):
    _inherit = 'stock.pack.operation.lot'

    br_supplier_id = fields.Many2one('res.partner', string="Supplier")
    br_removal_date = fields.Datetime(string="Expiry Date")
    lot_id = fields.Many2one('stock.production.lot', 'Expiry Date', oldname='lot_id')

    @api.model
    def default_get(self, fields):
        rec = super(StockPackOperationLot, self).default_get(fields)
        context = self._context
        if 'supplier_id' in context and context['supplier_id']:
            rec['br_supplier_id'] = self.env['res.partner'].browse(context['supplier_id']).id
        return rec

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        if self.lot_id:
            self.br_supplier_id = self.lot_id.br_supplier_id.id
            self.br_removal_date = self.lot_id.removal_date
