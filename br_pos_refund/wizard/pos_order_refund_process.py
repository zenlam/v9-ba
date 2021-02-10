# -*- encoding: utf-8 -*-
from openerp import models, api


class PosOrderRefundProcess(models.TransientModel):
    _name = 'pos.order.refund.process'

    @api.multi
    def action_refuse(self):
        pos_orders = self.env['pos.order'].browse(self.env.context.get('active_ids'))
        if pos_orders:
            pos_orders.action_refuse_cancel_request()

    @api.multi
    def action_approve(self):
        pos_orders = self.env['pos.order'].browse(self.env.context.get('active_ids'))
        if pos_orders:
            pos_orders.action_approve_cancel_request()
