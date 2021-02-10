from openerp import fields, models, api


class BRResCompany(models.Model):
    _inherit = 'res.company'

    sales_gst_adjustment_acc = fields.Many2one(comodel_name="account.account", required=True,
                                               string="Sales-Tax Adjustment Account")


BRResCompany()
