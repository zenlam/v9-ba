# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    api_attempts_count = fields.Integer(
        string='Number of Attempts of API Call',
        help='Number of attempts will be n+1',
        default=2)
    repeat_attempts_count = fields.Integer(
        string='Repeat Attempt After (mins)',
        default=3)
