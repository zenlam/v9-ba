from openerp import fields, models, api, _


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    manage_expirydate = fields.Boolean(string="Manage By Expiry Date", default=False)

    @api.multi
    def write(self, vals):
        if 'manage_expirydate' in vals:
            self.update_locations_manage_expirydate(vals['manage_expirydate'])
        return super(StockWarehouse, self).write(vals)

    def update_locations_manage_expirydate(self, manage_expirydate):
        """
        Update location's manage_expirydate accordingly to warehouse
        """
        for wh in self:
            locations = self.env['stock.location'].search([('id', 'child_of', wh.view_location_id.id)])
            locations.write({'manage_expirydate': manage_expirydate})
