from openerp import models, fields, api, _


class BrVehicle(models.Model):
    _name = 'br.fleet.vehicle'

    name = fields.Char(string="Vehicle Name", required=True)
    active = fields.Boolean(string="Active", default=True)
