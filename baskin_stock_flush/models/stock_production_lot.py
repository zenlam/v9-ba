# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    @api.multi
    def copy(self, default=None):
        if default is None:
            default = {}
        default.update({'name': ("%s (New)" % self.name)})
        return super(StockProductionLot, self).copy(default)
