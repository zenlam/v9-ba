from openerp import api, models, fields, _


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    display_name = fields.Char(string=_("Full Name"))
