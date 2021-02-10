# -*- coding: utf-8 -*-
from openerp import models, fields, api, _


class account_move_line_link(models.Model):
    _inherit = 'account.move.line'

    stock_move_id = fields.Many2one('stock.move')
    quant_ids = fields.Many2many('stock.quant')
    purchase_id = fields.Many2one('purchase.order', string="Purchase")
    invoice_line_id = fields.Many2one('account.invoice.line', string="Invoice Line")
