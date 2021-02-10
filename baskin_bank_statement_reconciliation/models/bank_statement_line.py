# -*- coding: utf-8 -*-

from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import logging
_logger = logging.getLogger(__name__) 

class bank_statement_reconcile_line(models.Model):
    _name = "bank.statement.reconcile.line"
    _order = 'date desc'

    is_reconcile = fields.Boolean('Reconcile')
    date = fields.Date(string='Date')
    ref = fields.Text(string='Reference')
    memo = fields.Char('Memo')
    name = fields.Char('Label')
    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='restrict')
    move_line_id = fields.Many2one('account.move.line', string='Journal Item')
    move_id = fields.Many2one('account.move', string='Journal Entry')
    move_line_id_string = fields.Text(string='Journal Item ids string')
    move_id_string = fields.Text(string='Journal Entry ids string')
    debit = fields.Monetary(default=0.0, currency_field='company_currency_id', digits=0)
    credit = fields.Monetary(default=0.0, currency_field='company_currency_id', digits=0)
    amount_currency = fields.Monetary(default=0.0, currency_field='company_currency_id', digits=0)
    bank_state = fields.Selection([('draft','Open'),('match','Matched')], default="draft", string="Bank Recon Status", readonly=True)
    company_currency_id = fields.Many2one('res.currency', readonly=True,
        help='Utility field to express amount currency')
    currency_id = fields.Many2one('res.currency', readonly=True,
        help='The optional other currency if it is a multi-currency entry')
    bank_statement_id = fields.Many2one('bank.statement.reconcile', string='Bank Statement')
    payment_id = fields.Many2one('account.payment', string="Originator Payment", help="Payment that created this entry")
    cheque_no = fields.Char(string="Cheque No", compute='get_cheque_no')

    @api.multi
    def get_cheque_no(self):
        for line in self:
            if line.move_line_id:
                line.cheque_no = line.move_line_id.cheque_no or ''
            else:
                if line.payment_id:
                    line.cheque_no = line.payment_id.cheque_no or ''

class bank_statement_reconcile_line_clone(models.Model):
    _name = "bank.statement.reconcile.line.clone"
    _inherit = "bank.statement.reconcile.line"
    _order = 'date desc'
    