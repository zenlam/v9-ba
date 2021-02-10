# -*- coding: utf-8 -*-

import xlwt
from cStringIO import StringIO
import base64
from datetime import datetime

from openerp import fields, models, api
from openerp import tools


class AccountBalanceExcelReport(models.TransientModel):
    _inherit = "account.balance.report"

    target_move = fields.Selection([('posted', 'All Posted Entries'),
                                    ('draft', 'All Unposted Entries'),
                                    ], string='Target Moves', required=True, default='posted')
    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)

    def _get_accounts(self, accounts, display_account):
        """ compute the balance, debit and credit for the provided accounts
            :Arguments:
                `accounts`: list of accounts record,
                `display_account`: it's used to display either all accounts or those accounts which balance is > 0
            :Returns a list of dictionary of Accounts with following key and value
                `name`: Account name,
                `code`: Account code,
                `credit`: total amount of credit,
                `debit`: total amount of debit,
                `balance`: total amount of balance,
        """
        account_result = {}
        # Prepare sql query base on selected parameters from wizard
        tables, where_clause, where_params = self.env['account.move.line']._query_get()
        tables = tables.replace('"', '')
        if not tables:
            tables = 'account_move_line'
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        # compute the balance, debit and credit for the provided accounts
        request = ("SELECT account_id AS id, SUM(debit) AS debit, SUM(credit) AS credit, (SUM(debit) - SUM(credit)) AS balance" +\
                   " FROM " + tables + " WHERE account_id IN %s " + filters + " GROUP BY account_id")
        params = (tuple(accounts.ids),) + tuple(where_params)
        self.env.cr.execute(request, params)
        for row in self.env.cr.dictfetchall():
            account_result[row.pop('id')] = row

        account_res = []
        for account in accounts:
            res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance'])
            currency = account.currency_id and account.currency_id or account.company_id.currency_id
            res['code'] = account.code
            res['name'] = account.name
            res['currency'] = ''
            if currency:
                res['currency'] = currency.symbol
            if account.id in account_result.keys():
                res['debit'] = account_result[account.id].get('debit')
                res['credit'] = account_result[account.id].get('credit')
                res['balance'] = account_result[account.id].get('balance')
            if display_account == 'all':
                account_res.append(res)
            if display_account == 'not_zero' and not currency.is_zero(res['balance']):
                account_res.append(res)
            if display_account == 'movement' and (not currency.is_zero(res['debit']) or not currency.is_zero(res['credit'])):
                account_res.append(res)
        return account_res

    @api.multi
    def _print_trial_balance_excel_report(self, data):
        self.model = data.get('model')
        docs = self.env[self.model].browse(self.env.context.get('active_ids', []))
        display_account = data['form'].get('display_account')
        accounts = docs if self.model == 'account.account' else self.env['account.account'].search([])
        return self.with_context(data['form'].get('used_context'))._get_accounts(accounts, display_account)

    @api.multi
    def check_report_excel(self):
        self.ensure_one()
        context = self._context
        data = {}
        company_name = ''
        user = self.env['res.users'].browse(context.get('uid'))
        if user:
            company_name = user.company_id.name
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['date_from', 'date_to', 'journal_ids', 'target_move','display_account'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        account_res = self._print_trial_balance_excel_report(data)
        workbook = xlwt.Workbook()
        fl = StringIO()
        worksheet = workbook.add_sheet('Trial-Balance')
        font = xlwt.Font()
        font.height = 200
        style = xlwt.easyxf('font: bold 1,height 270;')
        label_style = xlwt.easyxf('font: bold 1,height 200;')
        label_value = xlwt.XFStyle()
        label_value.font = font

        worksheet.col(1).width = 10000
        worksheet.col(2).width = 4000
        worksheet.col(3).width = 4000
        worksheet.col(4).width = 4000

        # worksheet.write_merge(2, 3, 2, 3, datetime.now().strftime("%Y-%m-%d %H:%M"), style)
        # worksheet.write_merge(2, 3, 10, 11, company_name, style)
        worksheet.write_merge(0, 2, 0, 2, company_name + ':' + 'Trial Balance', style)
        worksheet.write_merge(5, 5, 0, 2, 'Display Account:', label_style)
        worksheet.write_merge(6, 6, 0, 2, data['form']['display_account'], label_value)
        worksheet.write(5, 3, 'Date from :', label_style)
        worksheet.write(5, 4, data['form']['date_from'], label_value)
        worksheet.write(6, 3, 'Date to :', label_style)
        worksheet.write(6, 4, data['form']['date_to'], label_value)
        worksheet.write(5, 5, 'Target Moves:', label_style)
        worksheet.write(6, 5, data['form']['target_move'], label_value)
        worksheet.write(9, 0, 'Code', label_style)
        worksheet.write(9, 1, 'Account', label_style)
        worksheet.write(9, 2, 'Debit', label_style)
        worksheet.write(9, 3, 'Credit', label_style)
        worksheet.write(9, 4, 'Balance', label_style)
        row = 0
        colum = 10
        for res in account_res:
            worksheet.write(colum, row, res.get('code'))
            row += 1
            worksheet.write(colum, row, res.get('name'))
            row += 1
            worksheet.write(colum, row, tools.ustr(res.get('currency', '')) + ' ' + str(res.get('debit')))
            row += 1
            worksheet.write(colum, row, tools.ustr(res.get('currency', '')) + ' ' + str(res.get('credit')))
            row += 1
            worksheet.write(colum, row, tools.ustr(res.get('currency', '')) + ' ' + str(res.get('balance')))
            colum += 1
            row = 0

        workbook.save(fl)
        fl.seek(0)
        buf = base64.encodestring(fl.read())
        filename = "Trial-Balance"
        self.write({'file': buf, 'name': filename})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=account.balance.report&field=file&id=%s&filename=%s.xls' % (self.id, filename),
            'target': 'self',
            }
