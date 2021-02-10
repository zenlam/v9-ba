from openerp import models, fields, api, _


class PosSession(models.Model):
    _inherit = 'pos.session'

    def create_picking(self):
        """
        Create picking immediately for each pos_order if it is:
        - a transaction created to cancel another order from previous session (means we wont do this if user cancel transaction within that session)
        """
        for session in self:
            for order in session.order_ids:
                if order.is_refund and order.parent_id.session_id != order.session_id:
                    order.create_picking()
        return super(PosSession, self).create_picking()