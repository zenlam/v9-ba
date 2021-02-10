from openerp import fields, models, api, _


class br_account_register_payments(models.TransientModel):
    _inherit = 'account.register.payments'

    account_analytic_id = fields.Many2one(comodel_name='account.analytic.account', string=_("Analytic account"))

    # +1 for the hook :)
    def get_payment_vals(self):
        res = super(br_account_register_payments, self).get_payment_vals()
        res.update(account_analytic_id=self.account_analytic_id and self.account_analytic_id.id or False)
        return res

class br_account_payment(models.Model):
    _inherit = "account.payment"

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        if not self.invoice_ids:
            # Set default partner type for the payment type
            if self.payment_type == 'inbound':
                self.partner_type = 'customer'
            elif self.payment_type == 'outbound':
                self.partner_type = 'supplier'
        # Set payment method domain
        res = self._onchange_journal()
        if not res.get('domain', {}):
            res['domain'] = {}
        res['domain']['journal_id'] = self.payment_type == 'inbound' and [('at_least_one_inbound', '=', True)] or [
            ('at_least_one_outbound', '=', True)]
        res['domain']['journal_id'].append(('type', 'in', ('bank', 'cash')))
        res['domain']['journal_id'].append(('journal_user', '=', False))
        return res


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_trade_sales = fields.Boolean(string='Is Trade Sales?', default=False)
    is_default_refund = fields.Boolean(string='Default Refund Payment Method', default=False)