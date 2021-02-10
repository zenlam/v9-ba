# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_dispute = fields.Boolean("Is Dispute Picking")