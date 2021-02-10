# --*-- coding: utf-8 --*--

from openerp import fields, models


class account_tax(models.Model):
    _inherit = 'account.tax'

    tax_code = fields.Char(string="Code")
