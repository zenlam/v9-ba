from openerp import api, fields, models, SUPERUSER_ID, _


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    sequence_id = fields.Many2one(comodel_name='ir.sequence', string="Sequence")

    @api.model
    def create(self, vals):
        if 'name' in vals and 'code' in vals:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': vals['name'] + _(' Transfer Request Sequence'),
                'prefix': vals['code'] + '/RQ/',
                'padding': 5
            })
            vals['sequence_id'] = sequence.id
        return super(StockWarehouse, self).create(vals)

    @api.multi
    def write(self, vals):
        r = super(StockWarehouse, self).write(vals)
        if 'name' in vals or 'code' in vals:
            self.sequence_id.write({
                'name': self.name + _(' Transfer Request Sequence'),
                'prefix': vals.get('code', self.code) + '/RQ/',
                'padding': 5
            })
        return r
