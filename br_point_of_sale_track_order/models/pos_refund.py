from openerp import fields, models, api, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime

class PosRefundWizard(models.TransientModel):
    _inherit = 'br.confirm.refund.wizard'

    @api.multi
    def refund(self):
        self.save_activity_log()
        return super(PosRefundWizard, self).refund()

    def save_activity_log(self):
        """Save log from pos"""
        order = self.pos_order_id
        if order:
            vals = {
                'outlet_id': order.outlet_id.id,
                'pos_user': order.user_id.id,
                'invoice_no': order.pos_reference,
                'reference': order.pos_reference + " REFUND",
                'date': order.date_order,
            }
            lines = []
            for line in order.master_ids:
                l = {
                    'product_id': line.product_id.id,
                    'unit_price': line.price_unit,
                    'quantity': line.qty,
                    'reason': "cancel",
                    'date_log': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                    'cashier_id': self.env.user.id,
                }
                lines.append((0, 0, l))
            vals.update(line_ids=lines)
            self.env['pos.track.order'].create(vals)
