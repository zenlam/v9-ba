# --*-- coding: utf-8 --*--

from openerp import fields, api, models, _

class br_multi_outlet(models.Model):
    _inherit = 'br_multi_outlet.outlet'

    float_amount = fields.Float(string=_("Float Amount"))

