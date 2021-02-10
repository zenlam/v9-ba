# --*-- coding: utf-8 --*--
from openerp import fields, models, api, _
from openerp.exceptions import UserError
import time


class AccountBankStmtCashWizard(models.Model):
    """
    Account Bank Statement popup that allows entering cash details.
    """
    _inherit = 'account.bank.statement.cashbox'

    @api.multi
    def validate(self):
        bnk_stmt_id = self.env.context.get('bank_statement_id', False) or self.env.context.get('active_id', False)
        bnk_stmt = self.env['account.bank.statement'].browse(bnk_stmt_id)
        if bnk_stmt.pos_session_id:
            bnk_stmt.pos_session_id._try_lock_session()
            if bnk_stmt.pos_session_id.state == 'closed':
                raise UserError(_("Can't modified account bank statement belongs to closed session !"))
        super(AccountBankStmtCashWizard, self).validate()


class account_bank_statement(models.Model):
    _inherit = 'account.bank.statement'

    @api.multi
    def check_balance_end_real(self):
        for stm in self:
            pos_session = stm.pos_session_id
            if pos_session and pos_session.outlet_id.float_amount != 0:
                if pos_session.cash_register_balance_end_real == 0:
                    diff = pos_session.cash_register_balance_end - pos_session.outlet_id.float_amount
                else:
                    diff = pos_session.cash_register_balance_end_real - pos_session.outlet_id.float_amount
                if diff > 0:
                    raise UserError(
                        _("Please bank in an amount equal or greater than %s before closing this session." % diff))

    @api.multi
    def button_confirm_bank(self):
        self.check_balance_end_real()
        return super(account_bank_statement, self).button_confirm_bank()

    @api.multi
    def _balance_check(self):
        res = super(account_bank_statement, self)._balance_check()
        for stmt in self:
            if stmt.pos_session_id and stmt.journal_type == 'cash' and \
                    stmt.line_ids and not stmt.currency_id.is_zero(stmt.difference):
                values = {'ref': stmt.pos_session_id.name}
                for line in stmt.line_ids:
                    line.write(values)
        return res

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    credit_account_id = fields.Many2one(comodel_name='account.account')

    def _prepare_reconciliation_move_line(self, move, amount):
        values = super(AccountBankStatementLine, self)._prepare_reconciliation_move_line(move, amount)
        if move.statement_line_id and move.statement_line_id.credit_account_id:
            values.update(account_id=move.statement_line_id.credit_account_id.id)
        return values
