
from openerp import models, api, _
from openerp.exceptions import UserError

class AccountPaymentConfirm(models.TransientModel):
    """
       This wizard will confirm the all the selected draft payment
    """

    _name = "account.payment.confirm"
    _description = "Confirm the selected payment"

    @api.multi
    def payment_confirm(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['account.payment'].browse(active_ids):
            if record.state not in 'draft':
                raise UserError(
                    _("Selected payment(s) cannot be confirmed as they are not in 'Draft' state."))
            record.post()
        return {'type': 'ir.actions.act_window_close'}