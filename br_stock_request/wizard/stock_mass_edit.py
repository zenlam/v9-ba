from openerp import models, api, fields, _


class StockMassEdit(models.TransientModel):
    _name = 'stock.mass.edit'

    driver = fields.Many2one(string="Driver", comodel_name='res.partner', domain=[('type', '=', 'driver')])
    packer = fields.Many2one(string="Picker/Packer", comodel_name='res.partner', domain=[('type', '=', 'picker_packer')])
    truck = fields.Many2one(sring="Truck", comodel_name='br.fleet.vehicle')
    schedule_date = fields.Datetime(string="Schedule Date")

    @api.multi
    def edit_pickings(self):
        picking_ids = self.env.context.get('active_ids', False)
        if picking_ids:
            pickings = self.env['stock.picking'].browse(picking_ids).filtered(lambda x: x.state not in ('done', 'cancel'))
            vals = {}
            if self.driver:
                vals['driver'] = self.driver.id
            if self.truck:
                vals['vehicle'] = self.truck.id
            if self.packer:
                vals['packer'] = self.packer.id
            if self.schedule_date:
                vals['min_date'] = self.schedule_date
            if vals:
                pickings.write(vals)
