# --*-- coding: utf-8 --*--
from openerp import fields, models, api, _


class BRConfirmRefundWizard(models.TransientModel):
    _inherit = 'br.confirm.refund.wizard'

    @api.multi
    def refund(self):
        """ Call the sync cancel order function """
        res = super(BRConfirmRefundWizard, self).refund()
        order = self.pos_order_id
        # if the third party needs to sync the order data, then call the
        # void transaction function
        if order.third_party and order.third_party.sync_order_data:
            order.sync_cancel_transaction()
        return res
