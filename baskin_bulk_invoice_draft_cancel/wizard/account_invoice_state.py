# -*- coding: utf-8 -*-
from openerp import models, api, _
from openerp.exceptions import UserError


class AccountInvoiceDraft(models.TransientModel):
    """
    This wizard will set the all the selected open invoices to draft again.
    """

    _name = "account.invoice.draft"
    _description = "Set the Selected Invoices to Draft State"

    @api.multi
    def invoice_draft(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        for record in self.env['account.invoice'].browse(active_ids):
            if record.state == 'cancel':
                record.action_cancel_draft()
            elif record.state == 'open':
                record.signal_workflow('invoice_cancel')
                record.action_cancel_draft()
            else:
                raise UserError(_("Selected invoice(s) cannot be drafted as they are not in 'Open' or 'Cancel' state."))
        return {'type': 'ir.actions.act_window_close'}

