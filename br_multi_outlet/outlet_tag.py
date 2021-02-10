from openerp import models, fields, api, _

class br_outlet_tag(models.Model):
    _name = 'br.outlet.tag'

    name = fields.Char(string=_("Name"))
    color = fields.Integer('Color Index')

