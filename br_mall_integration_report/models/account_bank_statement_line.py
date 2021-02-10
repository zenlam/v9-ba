from openerp import models, fields, _, api


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    pos_date_order = fields.Datetime(related='pos_statement_id.date_order',
                                     string='POS Order Date',
                                     store=True)
