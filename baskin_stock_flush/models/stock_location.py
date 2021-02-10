# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class StockLocation(models.Model):
    _inherit = "stock.location"

    is_flush_location = fields.Boolean(string='Is Flush Location',
                                       default=False)
