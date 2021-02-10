# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_dispute_picking = fields.Boolean(related='picking_type_id.is_dispute', string='Dispute Picking', store=True)
