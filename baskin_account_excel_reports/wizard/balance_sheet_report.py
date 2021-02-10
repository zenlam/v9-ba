from openerp import models, fields, api, _
import xlwt
from xlwt import Alignment, XFStyle
from openerp.exceptions import ValidationError
from cStringIO import StringIO
import base64
from datetime import datetime, timedelta
from collections import OrderedDict


def accumulate(lis):
    total = 0
    for x in lis:
        total += x
        yield total


def getMonthsInRange(startDate, endDate, format=False):
    start = datetime.strptime(startDate, "%Y-%m-%d")
    end = datetime.strptime(endDate, "%Y-%m-%d")
    if format:
        return OrderedDict(((start + timedelta(_)).strftime(r"%m/%Y"), None) for _ in xrange((end - start).days+1)).keys()
    else:
        return OrderedDict(((start + timedelta(_)).strftime(r"%b-%y"), None) for _ in xrange((end - start).days+1)).keys()


class AccountingExcelReport(models.TransientModel):
    _inherit = 'accounting.report'

    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)

    def get_start_date(self, data):
        """
        get the start date (first day) of the fiscal year
        :param data:
        :return:
        """
        current_year = int(data['date_from'][:4])
        # get the fiscal date for that year
        fiscal_date = datetime(year=current_year, month=self.company_id.fiscalyear_last_month,
                                     day=self.company_id.fiscalyear_last_day) + timedelta(days=1)
        start_date = datetime.strptime(data['date_from'], '%Y-%m-%d')

        # if the start date in report is earlier than the fiscal date, use the fiscal date of previous year.
        if start_date < fiscal_date:
            fiscal_year = current_year - 1
        else:
            fiscal_year = current_year

        final_fiscal_date = datetime(year=fiscal_year, month=self.company_id.fiscalyear_last_month,
                              day=self.company_id.fiscalyear_last_day) + timedelta(days=1)
        return final_fiscal_date.strftime("%Y-%m-%d")

    def get_accumulate_balance(self, data, value):
        """
        return a dict containing the accumulate balance for month
        :param value:
        :return:
        """
        month_balance = []
        start_date = self.get_start_date(data)
        end_date = data['date_to']
        # get the month from the first day of the fiscal year to the month of end_date
        month_dict = getMonthsInRange(start_date, end_date)

        # store the balance of every month into the list
        for month in month_dict:
            month_balance.append(value[month]['balance'])
        # accumulate the balance from the first month until the last month
        vals_balance = list(accumulate(month_balance))
        # map the accumulated balance to the particular month
        balance_dict = dict(zip(month_dict, vals_balance))
        return balance_dict

    def _compute_account_balance(self, accounts, data):
        """ compute the balance, debit and credit for the provided accounts
        """
        mapping = {
            'balance': "COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance",
        }
        start_date = self.get_start_date(data)
        end_date = data['date_to']

        res = {}
        res_dict = {}
        month_dict = {}
        for account in accounts:
            res[account.id] = dict((fn, 0.0) for fn in mapping.keys())
            for date in getMonthsInRange(start_date, end_date):
                month_dict[date] = dict((fn, 0.0) for fn in mapping.keys())
                res_dict[account.id] = dict(month_dict)

        if accounts:
            ctx = dict(self._context or {})
            # for date in getMonthsInRange(start_date, end_date, True):
#             month = datetime.strptime(date, '%m/%Y').month
#             year = datetime.strptime(date, '%m/%Y').year
#             num_days = calendar.monthrange(year, month)
#             start_date = datetime.strptime(date, '%m/%Y').replace(day=1)
#             end_date = datetime.strptime(date, '%m/%Y').replace(day=num_days[1])
#             ctx['date_from'] = start_date.strftime('%Y-%m-%d')
#             ctx['date_to'] = end_date.strftime('%Y-%m-%d')
            ctx['date_from'] = start_date
            ctx['date_to'] = end_date
            tables, where_clause, where_params = self.env['account.move.line'].with_context(ctx)._query_get()
            tables = tables.replace('"', '') if tables else "account_move_line"
            wheres = [""]
            if where_clause.strip():
                wheres.append(where_clause.strip())
            filters = " AND ".join(wheres)
            request = "SELECT account_id as id, " + ', '.join(mapping.values()) +  \
                      ",date_trunc('month', account_move_line.date) as txn_month  FROM " + tables + \
                      " WHERE account_id IN %s " \
                      + filters + \
                      " GROUP BY account_id, txn_month"
            params = (tuple(accounts._ids),) + tuple(where_params)
            self.env.cr.execute(request, params)
            for row in self.env.cr.dictfetchall():
                res_dict[row['id']][row['txn_month'].strftime('%b-%y')]['balance'] = row['balance']
        return res_dict

    def _compute_report_balance(self, reports, data):
        res = {}
        start_date = self.get_start_date(data)
        end_date = data['date_to']
        fields = ['balance']
        for report in reports:
            if report.id in res:
                continue
            month_dict = {}
            for date in getMonthsInRange(start_date, end_date):
                month_dict[date] = dict((fn, 0.0) for fn in fields)
                res[report.id] = dict(month_dict)
            if report.type == 'accounts':
                # it's the sum of the linked accounts
                res[report.id]['account'] = self._compute_account_balance(report.account_ids, data)
                for value in res[report.id]['account'].values():
                    for range in getMonthsInRange(start_date, end_date):
                        res[report.id][range]['balance'] += value[range]['balance']
            elif report.type == 'account_type':
                # it's the sum the leaf accounts with such an account type
                accounts = self.env['account.account'].search([('user_type_id', 'in', report.account_type_ids.ids)])
                res[report.id]['account'] = self._compute_account_balance(accounts, data)
                for value in res[report.id]['account'].values():
                    for range in getMonthsInRange(start_date, end_date):
                        res[report.id][range]['balance'] += value[range]['balance']
            elif report.type == 'account_report' and report.account_report_id:
                # it's the amount of the linked report
                res2 = self._compute_report_balance(report.account_report_id, data)
                for key, value in res2.items():
                    for range in getMonthsInRange(start_date, end_date):
                        res[report.id][range]['balance'] += value[range]['balance']
            elif report.type == 'sum':
                # it's the sum of the children of this account.report
                res2 = self._compute_report_balance(report.children_ids, data)
                for key, value in res2.items():
                    for range in getMonthsInRange(start_date, end_date):
                        res[report.id][range]['balance'] += value[range]['balance']
        return res

    def get_account_lines(self, data):
        lines = []
        account_report = self.env['account.financial.report'].search([('id', '=', data['account_report_id'])])
        child_reports = account_report._get_children_by_order()
        start_date = data['date_from']
        end_date = data['date_to']
        res = self.with_context(data.get('used_context'))._compute_report_balance(child_reports, data)
        for report in child_reports:
            ratio_dict = dict({})
            temp_value = {}
            vals = {
                'rec_id': report.id,
                'name': report.name,
                'code': report.sequence,
                'type': 'report',
                'parent_id': False,
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type or False,  # used to underline the financial report balances
            }
            if vals['code'] == 0:
                vals['code'] = ''
            if vals['level'] == 1 and report.parent_id:
                vals['parent_id'] = report.parent_id.id
            # store the balance of every month into a temporary list
            for date in getMonthsInRange(self.get_start_date(data), end_date):
                temp_value[date] = {'balance': res[report.id][date]['balance'] * report.sign}
            # accumulate the balance
            bal_dict = self.get_accumulate_balance(data, temp_value)
            for date in getMonthsInRange(start_date, end_date):
                # pass the value from the accumulated temporary list to vals
                vals[date] = bal_dict[date]
                vals[date + '- Ratio %'] = 0
            lines.append(vals)
            if report.display_detail == 'no_detail':
                # the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue
            if res[report.id].get('account'):
                sub_lines = []
                for account_id, value in res[report.id]['account'].items():
                    # if there are accounts to display, we add them to the lines with a level equals to their level in
                    # the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                    # financial reports for Assets, liabilities...)
                    account = self.env['account.account'].browse(account_id)
                    vals = {
                        'name': account.name,
                        'code': account.code,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and 4,
                        'account_type': account.internal_type,
                    }
                    # accumulate the balance
                    balance_dict = self.get_accumulate_balance(data, value)
                    for date in getMonthsInRange(start_date, end_date):
                        # the total balance of the month should be same as the balance after accumulating
                        value[date]['balance'] = balance_dict[date]
                        if report.level and report.parent_id:
                            ratio_dict[date + '- Ratio %'] = bal_dict[date]
                        acc_total = value[date]['balance']
                        ratio_total = ratio_dict[date + '- Ratio %']
                        vals[date + '- Ratio %'] = 0
                        if int(ratio_total) != 0:
                            vals[date + '- Ratio %'] = round((acc_total / ratio_total) * 100, 2)
                        vals[date] = value[date]['balance']
                    sub_lines.append(vals)
                lines += sorted(sub_lines, key=lambda sub_line: sub_line['name'])
        return lines

    @api.multi
    def check_balance_sheet_report_excel(self):
        data = self.check_report()
        if data.get('data'):
            data['data']['form'].update(self.read(['date_from_cmp', 'debit_credit', 'date_to_cmp', 'filter_cmp', 'account_report_id', 'enable_filter', 'label_filter', 'target_move'])[0])
            for field in ['account_report_id']:
                if isinstance(data['data']['form'][field], tuple):
                    data['data']['form'][field] = data['data']['form'][field][0]
        date_from = data['data']['form']['date_from']
        date_to = data['data']['form']['date_to']
        chk_date_from = datetime.strptime(date_from, '%Y-%m-%d')
        chk_date_to = datetime.strptime(date_to, '%Y-%m-%d')
        if chk_date_from > chk_date_to:
            raise ValidationError(_('Please enter date from bigger then date to!!!!'))
        if chk_date_from == chk_date_to:
            raise ValidationError(_('Please enter date from bigger then date to!!!'))
        report_lines = self.get_account_lines(data['data']['form'])
        if data.get('context'):
            company_name = ''
            user = self.env['res.users'].browse(data['context']['uid'])
            if user:
                company_name = user.company_id.name

        workbook = xlwt.Workbook()
        fl = StringIO()
        worksheet = workbook.add_sheet('Balance-Sheet')
        font = xlwt.Font()
        font.height = 200
        al = Alignment()
        al.horz = Alignment.HORZ_RIGHT
        style_align = XFStyle()
        style_align.alignment = al
        style = xlwt.easyxf('font: bold 1,height 200;')
        title_style = xlwt.easyxf('font: bold 1,height 200;')
        # label_style = xlwt.easyxf('font: bold 1,height 150;')
        label_value = xlwt.XFStyle()
        label_value.font = font
        col_width = 4000
        row_height = 400

        # Headers
        worksheet.col(1).width = 10000
        # worksheet.col(2).width = col_width
        # worksheet.row(2).height = row_height

        month_ratio_list = []
        for res in getMonthsInRange(date_from, date_to):
            month_val = res.split('-')[0]
            ratio_val = month_val + '- Ratio %'
            month_ratio_list.append(res)
            month_ratio_list.append(ratio_val)

        # Company Details
        worksheet.write_merge(0, 0, 0, 1, company_name, title_style)
        # worksheet.write_merge(3, 3, 0, 2, 'Display Account:', label_style)
        # worksheet.write_merge(4, 4, 0, 2, data['data']['form']['display_account'], label_value)
        worksheet.write(3, 0, 'Date from :', title_style)
        worksheet.write(3, 1, data['data']['form']['date_from'])
        worksheet.write(4, 0, 'Date to :', title_style)
        worksheet.write(4, 1, data['data']['form']['date_to'])
        worksheet.write(3, 2, 'Target Moves:', title_style)
        worksheet.write(4, 2, data['data']['form']['target_move'])

        worksheet.write_merge(6, 6, 0, 3, "Statement of Financial Position as at " + datetime.now().strftime("%Y-%m-%d %H:%M"), title_style)

        worksheet.write(8, 0, 'Code', style)
        # worksheet.col(3).width = col_width
        worksheet.write(8, 1, 'Account', style)
        m_col = 2
        for month in month_ratio_list:
            # worksheet.col(m_col).width = col_width
            # worksheet.row(2).height = row_height
            worksheet.write(8, m_col, month, style)
            m_col += 1
        row = 9
        col = 0
        for line in report_lines:
            if line.get('level') != 0:
                # worksheet.row(row).height = row_height
                if line.get('level') == 1:
                    col = col + 1
                    worksheet.col(col).width = col_width
                    worksheet.write(row, col, line['name'], title_style)
                elif not line.get('level') > 3:
                    worksheet.col(col).width = col_width
                    worksheet.write(row, col, line['code'])
                    col = col + 1
                    worksheet.col(col).width = col_width
                    worksheet.write(row, col, line['name'])
                else:
                    worksheet.col(col).width = col_width
                    worksheet.write(row, col, line['code'])
                    col = col + 1
                    worksheet.col(col).width = col_width
                    worksheet.write(row, col, line['name'])

                for month in getMonthsInRange(date_from, date_to):
                    col += 1
                    worksheet.col(col).width = col_width
                    worksheet.write(row, col, line[month])
                    col += 1
                    if line.get('level') > 3:
                        worksheet.col(col).width = col_width
                        worksheet.write(row, col, str(line[month + '- Ratio %']) + '%', style_align)
                row += 1
                col = 0
        workbook.save(fl)
        fl.seek(0)
        buf = base64.encodestring(fl.read())
        filename = "Balance-Sheet"
        self.write({'file': buf, 'name': filename})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=accounting.report&field=file&id=%s&filename=%s.xls' % (self.id, filename),
            'target': 'self',
        }


class Accounts(models.Model):
    _inherit = 'account.account'

    def _get_children_by_order(self):
        '''returns a recordset of all the children computed recursively, and sorted by sequence. Ready for the printing'''
        res = self
        children = self.search([('parent_id', 'in', self.ids)])
        if children:
            for child in children:
                res += child._get_children_by_order()
        return res
