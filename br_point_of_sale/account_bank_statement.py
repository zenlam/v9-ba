# -*- coding: utf-8 -*-
__author__ = 'truongnn'
import re
from datetime import datetime, timedelta

from openerp import models, api, tools
from openerp.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def _prepare_reconciliation_move_line(self, move, amount):
        """ - Add Analytic Account to Create move line
            - Prepare the dict of values to create the move line from a statement line.
            :param recordset move: the account.move to link the move line
            :param float amount: the amount of transaction that wasn't already reconciled
        """
        res = super(AccountBankStatementLine, self)._prepare_reconciliation_move_line(move, amount)

        # TruongNN
        session = self.statement_id.pos_session_id
        if session:
            if session.rescue:
                pattern = "RESCUE FOR (.+?)\)"
                match = re.search(pattern, session.name)
                if match:
                    session = None
                    session_name = match.group(1)
                    session = self.env['pos.session'].search([('name', '=', session_name)])

            d = datetime.strptime(session.start_at, tools.DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(hours=8)
            res.update(date=d.strftime(tools.DEFAULT_SERVER_DATE_FORMAT))
            outlet = session.outlet_id
            analytic_account_id = outlet and outlet.analytic_account_id and outlet.analytic_account_id.id or False
            if analytic_account_id:
                res.update({'analytic_account_id': analytic_account_id})
        # TruongNN
        return res

    def fast_counterpart_creation(self):
        lines = self
        if self.env.context.get('skip_pos_order_statement', False):
            lines = lines.filtered(lambda x: not x.pos_statement_id)
        for st_line in lines:
            # Technical functionality to automatically reconcile by creating a new move line
            vals = {
                'name': st_line.name,
                'debit': st_line.amount < 0 and -st_line.amount or 0.0,
                'credit': st_line.amount > 0 and st_line.amount or 0.0,
                'account_id': st_line.account_id.id,
            }
            # TruongNN
            outlet = self.statement_id.pos_session_id.outlet_id
            analytic_account_id = outlet and outlet.analytic_account_id and outlet.analytic_account_id.id or False
            if analytic_account_id:
                vals.update({'analytic_account_id': analytic_account_id})
            # TruongNN
            st_line.process_reconciliation(new_aml_dicts=[vals])

    @api.model
    def create(self, vals):
        if 'name' in vals and 'return' in vals['name']:
            pos_order = self.env['pos.order'].browse(vals['pos_statement_id'])
            vals.update(date=pos_order.date_order.split(' ')[0])
        return super(AccountBankStatementLine, self).create(vals)
