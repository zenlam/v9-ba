from openerp import fields, api, models, _


class StockLocation(models.Model):
    _inherit = 'stock.location'

    manage_expirydate = fields.Boolean(string="Manage By Expiry Date", default=True)
