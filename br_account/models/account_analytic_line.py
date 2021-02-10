from openerp import models, fields, api
from math import copysign


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    analytic_amount_currency = fields.Monetary(string='Amount Currency', compute="_get_analytic_amount_currency",
                                               help="The amount expressed in the related account currency "
                                                    "if not equal to the company one.",
                                               readonly=True)

    @api.model
    def _get_analytic_amount_currency(self):
        self.analytic_amount_currency = abs(self.amount_currency) * copysign(1, self.amount)

AccountAnalyticLine()
