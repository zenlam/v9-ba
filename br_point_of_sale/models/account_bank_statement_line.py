# -*- coding: utf-8 -*-

from openerp import models, fields, api, _


class BankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    approval_no = fields.Char(string='Approval No')
    terminal_id = fields.Char(string='Card Terminal ID')
    card_number = fields.Char(string='Card Number')
    card_type = fields.Char(string='Card Type')
    transaction_inv_number = fields.Char(string='Terminal Invoice Number')
    transaction_datetime = fields.Datetime(string='Terminal Transaction '
                                                  'Datetime')
    merchant_id = fields.Char(string='Merchant ID')
    acquirer_name = fields.Char(string='Bank Acquirer Name')
    acquirer_code = fields.Char(string='Bank Acquirer Code')
    settlement_batch_number = fields.Char(string='Settlement Batch No.')

    @api.multi
    def get_masked_card_number(self):
        self.ensure_one()
        number_length = len(self.card_number)
        result = '*' * (number_length - 4)
        return result + self.card_number[-4:]
