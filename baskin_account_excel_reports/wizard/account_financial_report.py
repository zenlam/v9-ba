# -*- coding: utf-8 -*-

import base64
from collections import OrderedDict
from cStringIO import StringIO
from datetime import datetime, timedelta
import xlsxwriter

from openerp import api, fields, models, _
from openerp.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class AccountingAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    
    is_department = fields.Boolean('Is Department')
    
def getMonthsInRange(startDate, endDate, format=False):
    start = datetime.strptime(startDate, "%Y-%m-%d")
    end = datetime.strptime(endDate, "%Y-%m-%d")
    return OrderedDict(((start + timedelta(mon)).strftime("%Y-%m"), None) for mon in xrange((end - start).days + 1)).keys()


class AccountingReport(models.TransientModel):
    _inherit = 'accounting.report'

    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)
    report_type = fields.Selection([
                    ('pl_by_month', 'P&L By Month'),
                    ('pl_by_outlet_month', 'P&L By Outlet By Month'),
                    ('pl_by_department_month', 'P&L By Department By Month'),
                    ('ytd_pl_by_outlet', 'YTD P&L By Outlet')],
                    string='Report Type',
                    default='pl_by_month')
    outlet_id = fields.Many2one('br_multi_outlet.outlet', string='Outlet')
    account_analytic_ids = fields.Many2many('account.analytic.account', string='Department', domain=[('is_department','=',True)])
    target_move = fields.Selection([('posted', 'All Posted Entries'),
                                    ('draft', 'All Unposted Entries'),
                                    ], string='Target Moves', required=True, default='posted')

    def _compute_account_balance_pl(self, accounts, data):
        """ compute the balance, debit and credit for the provided accounts
        """
        mapping = {
            'balance': "COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance",
            'debit': "COALESCE(SUM(debit), 0) as debit",
            'credit': "COALESCE(SUM(credit), 0) as credit",
        }
        start_date = data['date_from']
        end_date = data['date_to']

        res = {}
        res_dict = {}
        month_dict = {}

        outlets = self._get_outlet()
        departments = self._get_department_month(data)
        months = getMonthsInRange(start_date, end_date)

        for account in accounts:
            res[account.id] = dict((fn, 0.0) for fn in mapping.keys())
            if data['report_type'] == 'ytd_pl_by_outlet':
                for outlet in outlets:
                    month_dict[outlet] = dict((fn, 0.0) for fn in mapping.keys())
                    res_dict[account.id] = dict(month_dict)
            elif data['report_type'] == 'pl_by_department_month':
                for department in departments:
                    month_dict[department] = dict((fn, 0.0) for fn in mapping.keys())
                    res_dict[account.id] = dict(month_dict)
            else:
                for date in months:
                    month_dict[date] = dict((fn, 0.0) for fn in mapping.keys())
                    res_dict[account.id] = dict(month_dict)

        if accounts:
            ctx = dict(self._context or {})
            ctx['date_from'] = start_date
            ctx['date_to'] = end_date
            tables, where_clause, where_params = self.env['account.move.line'].with_context(ctx)._query_get()
            tables = tables.replace('"', '') if tables else "account_move_line"
            wheres = [""]
            if where_clause.strip():
                wheres.append(where_clause.strip())
            filters = " AND ".join(wheres)
            if data['report_type'] == 'pl_by_outlet_month':
                Br_Outlet = self.env['br_multi_outlet.outlet']
                analytic_account_id = [Br_Outlet.browse(data['outlet_id']).analytic_account_id.id]
                # filters += " AND analytic_account_id "
                request = "SELECT account_id as id, " + ', '.join(mapping.values()) +  \
                          ", to_char(account_move_line.date, 'YYYY-MM') as txn_month  FROM " + tables + \
                          " WHERE account_id IN %s " \
                          + filters + " AND account_move_line.analytic_account_id in %s"  \
                          " GROUP BY account_id, txn_month"
                params = (tuple(accounts._ids),) + tuple(where_params) + (tuple(analytic_account_id),)
                
            elif data['report_type'] == 'pl_by_department_month':
                analytic_account_id = data['account_analytic_ids']
                # filters += " AND analytic_account_id "
                #", to_char(account_move_line.date, 'YYYYMM') as txn_month  FROM " + tables + \
                request = "SELECT account_id as id, " + ', '.join(mapping.values()) +  \
                          ", to_char(account_move_line.date, 'YYYY-MM')|| '0' || ' ' || aac.name as txn_month  FROM " + tables + \
                          " LEFT JOIN account_analytic_account as aac on account_move_line.analytic_account_id = aac.id" \
                          " WHERE account_id IN %s " \
                          + filters + " AND account_move_line.analytic_account_id in %s"  \
                          " GROUP BY account_id, txn_month order by txn_month"
                params = (tuple(accounts._ids),) + tuple(where_params) + (tuple(analytic_account_id),)
                
                for group_config in self.env['analytic.group'].search([('analytic_account_ids','!=',False)]):
                    if group_config.enable_pl_grouping:
                        # group into one column
                        analytic_group_q = "SELECT account_id as id, " + ', '.join(mapping.values()) +  \
                              ", to_char(account_move_line.date, 'YYYY-MM')|| {sequence} || ' ' || '{group_name}' as txn_month  FROM ".format(group_name = group_config.name,sequence=group_config.sequence) + tables + \
                              " LEFT JOIN account_analytic_account as aac on account_move_line.analytic_account_id = aac.id" \
                              " WHERE account_id IN %s " \
                              + filters + " AND account_move_line.analytic_account_id in %s"  \
                              " GROUP BY account_id, txn_month order by txn_month"
                        analytic_params = (tuple(accounts._ids),) + tuple(where_params) + (tuple(list(set(group_config.analytic_account_ids.ids) - set(analytic_account_id))),)
                    else:
                        # one column for each analytic account
                        analytic_group_q = "SELECT account_id as id, " + ', '.join(mapping.values()) +  \
                              ", to_char(account_move_line.date, 'YYYY-MM')|| {sequence} || ' ' || aac.name as txn_month  FROM ".format(sequence=group_config.sequence) + tables + \
                              " LEFT JOIN account_analytic_account as aac on account_move_line.analytic_account_id = aac.id" \
                              " WHERE account_id IN %s " \
                              + filters + " AND account_move_line.analytic_account_id in %s"  \
                              " GROUP BY account_id, txn_month order by txn_month"
                        analytic_params = (tuple(accounts._ids),) + tuple(where_params) + (tuple(list(set(group_config.analytic_account_ids.ids) - set(analytic_account_id))),)
                    self.env.cr.execute(analytic_group_q, analytic_params)
                    rows_group = self.env.cr.dictfetchall()
                    for row in rows_group:
                        res_dict[row['id']][row['txn_month']]['balance'] += row['balance']
                        res_dict[row['id']][row['txn_month']]['debit'] += row['debit']
                        res_dict[row['id']][row['txn_month']]['credit'] += row['credit']    
                    

            elif data['report_type'] == 'ytd_pl_by_outlet':
                request = "SELECT account_id as id, " + ', '.join(mapping.values()) +  \
                          ", outlet.code AS txn_month" \
                          " FROM " + tables + \
                          " LEFT JOIN br_multi_outlet_outlet outlet on outlet.analytic_account_id = account_move_line.analytic_account_id" \
                          " WHERE account_id IN %s " \
                          " AND outlet.code IS NOT NULL" \
                          + filters +  \
                          " GROUP BY account_id, txn_month"
                params = (tuple(accounts._ids),) + tuple(where_params)
            else:
                request = "SELECT account_id as id, " + ', '.join(mapping.values()) +  \
                      ", to_char(account_move_line.date, 'YYYY-MM') as txn_month  FROM " + tables + \
                      " WHERE account_id IN %s " \
                      + filters + \
                      " GROUP BY account_id, txn_month"
                params = (tuple(accounts._ids),) + tuple(where_params)
            self.env.cr.execute(request, params)
            rows = self.env.cr.dictfetchall()
            for row in rows:
                res_dict[row['id']][row['txn_month']]['balance'] += row['balance']
                res_dict[row['id']][row['txn_month']]['debit'] += row['debit']
                res_dict[row['id']][row['txn_month']]['credit'] += row['credit']
        return res_dict

    def _compute_report_balance_pl(self, reports, data):
        res = {}
        start_date = data['date_from']
        end_date = data['date_to']
        fields = ['credit', 'debit', 'balance']
        months = getMonthsInRange(start_date, end_date)
        for report in reports:
            if report.id in res:
                continue
            month_dict = {}
            for date in months:
                month_dict[date] = dict((fn, 0.0) for fn in fields)
                res[report.id] = dict(month_dict)
            if report.type == 'accounts':
                # it's the sum of the linked accounts
                res[report.id]['account'] = self._compute_account_balance_pl(report.account_ids, data)
                for value in res[report.id]['account'].values():
                    for month in months:
                        for field in fields:
                            res[report.id][month][field] += value[month][field] # * report.sign
            elif report.type == 'account_type':
                # it's the sum the leaf accounts with such an account type
                accounts = self.env['account.account'].search([('user_type_id', 'in', report.account_type_ids.ids)])
                res[report.id]['account'] = self._compute_account_balance_pl(accounts, data)
                for value in res[report.id]['account'].values():
                    for field in fields:
                        for month in months:
                            res[report.id][month][field] += value[month][field] # * report.sign
            elif report.type == 'account_report' and report.account_report_id:
                # it's the amount of the linked report
                res2 = self._compute_report_balance_pl(report.account_report_id, data)
                for key, value in res2.items():
                    for month in months:
                        for field in fields:
                            res[report.id][month][field] += value[month][field] # * report.sign
            elif report.type == 'sum':
                # it's the sum of the children of this account.report
                res2 = self._compute_report_balance_pl(report.children_ids, data)
                for key, value in res2.items():
                    for month in months:
                        for field in fields:
                            res[report.id][month][field] += value[month][field] # * report.sign
        return res

    def _get_outlet(self):
        BrOutlet = self.env['br_multi_outlet.outlet']
        StockWarehouse = self.env['stock.warehouse']
        outlets = BrOutlet.search([])
        outlet_codes = [outlet.code for outlet in outlets]

        # warehouses = StockWarehouse.search([])
        # warehouses_names = [warehouse.code for warehouse in warehouses]
        # outlet_codes.extend(warehouses_names)
        return list(set(outlet_codes))

    def _compute_report_balance_outlet(self, reports, data):
        res = {}
        fields = ['credit', 'debit', 'balance']
        outlets = self._get_outlet()
        for report in reports:
            if report.id in res:
                continue
            outlet_dict = {}

            for date in outlets:
                outlet_dict[date] = dict((fn, 0.0) for fn in fields)
                res[report.id] = dict(outlet_dict)
            if report.type == 'accounts':
                # it's the sum of the linked accounts
                res[report.id]['account'] = self._compute_account_balance_pl(report.account_ids, data)
                for value in res[report.id]['account'].values():
                    for outlet in outlets:
                        for field in fields:
                            res[report.id][outlet][field] += value[outlet][field] # * report.sign
            elif report.type == 'account_type':
                # it's the sum the leaf accounts with such an account type
                accounts = self.env['account.account'].search([('user_type_id', 'in', report.account_type_ids.ids)])
                res[report.id]['account'] = self._compute_account_balance_pl(accounts, data)
                for value in res[report.id]['account'].values():
                    for field in fields:
                        for outlet in outlets:
                            res[report.id][outlet][field] += value[outlet][field] # * report.sign
            elif report.type == 'account_report' and report.account_report_id:
                # it's the amount of the linked report
                res2 = self._compute_report_balance_outlet(report.account_report_id, data)
                for key, value in res2.items():
                    for outlet in outlets:
                        for field in fields:
                            res[report.id][outlet][field] += value[outlet][field] # * report.sign
            elif report.type == 'sum':
                # it's the sum of the children of this account.report
                res2 = self._compute_report_balance_outlet(report.children_ids, data)
                for key, value in res2.items():
                    for outlet in outlets:
                        for field in fields:
                            res[report.id][outlet][field] += value[outlet][field]
        return res
    
    def _get_department_month(self,data):
        analytics = self.env['account.analytic.account']
        months = getMonthsInRange(data['date_from'], data['date_to'])
        selected_analytic = analytics.browse(data['account_analytic_ids'])
        dept_month = []
        if data['account_analytic_ids']:
            for date in months:
                dept_month += [date + '0' + ' ' + analytic.name for analytic in selected_analytic] 
        for group_config in self.env['analytic.group'].search([]):
            if group_config.enable_pl_grouping:
                for date in months:
                    dept_month += [date + str(group_config.sequence) + ' ' + group_config.name]
            else:
                for account in group_config.analytic_account_ids.filtered(lambda x: x.id not in [x.id for x in selected_analytic]):
                    for date in months:
                        dept_month += [date + str(group_config.sequence) + ' ' + account.name]
        return dept_month

    def _compute_report_balance_department(self, reports, data):
        res = {}
        fields = ['credit', 'debit', 'balance']
        departments = self._get_department_month(data)
        for report in reports:
            if report.id in res:
                continue
            department_dict = {}

            for date in departments:
                department_dict[date] = dict((fn, 0.0) for fn in fields)
                res[report.id] = dict(department_dict)
            
            if report.type == 'accounts':
                # it's the sum of the linked accounts
                res[report.id]['account'] = self._compute_account_balance_pl(report.account_ids, data)
                for value in res[report.id]['account'].values():
                    for department in departments:
                        for field in fields:
                            res[report.id][department][field] += value[department][field] # * report.sign
            elif report.type == 'account_type':
                # it's the sum the leaf accounts with such an account type
                accounts = self.env['account.account'].search([('user_type_id', 'in', report.account_type_ids.ids)])
                res[report.id]['account'] = self._compute_account_balance_pl(accounts, data)
                for value in res[report.id]['account'].values():
                    for field in fields:
                        for department in departments:
                            res[report.id][department][field] += value[department][field] # * report.sign
            elif report.type == 'account_report' and report.account_report_id:
                # it's the amount of the linked report
                res2 = self._compute_report_balance_department(report.account_report_id, data)
                for key, value in res2.items():
                    for department in departments:
                        for field in fields:
                            res[report.id][department][field] += value[department][field] # * report.sign
            elif report.type == 'sum':
                # it's the sum of the children of this account.report
                res2 = self._compute_report_balance_department(report.children_ids, data)
                for key, value in res2.items():
                    for department in departments:
                        for field in fields:
                            res[report.id][department][field] += value[department][field]
        return res

    def get_account_lines_pl(self, data):
        lines = []
        account_report = self.env['account.financial.report'].search([('id', '=', data['account_report_id'])])
        child_reports = account_report._get_children_by_order()
        start_date = data['date_from']
        end_date = data['date_to']

        months = []
        outlets = []
        departments = []

        if data['report_type'] == 'ytd_pl_by_outlet':
            res = self.with_context(data.get('used_context'))._compute_report_balance_outlet(child_reports, data)
            outlets = self._get_outlet()
        elif data['report_type'] == 'pl_by_department_month':
            res = self.with_context(data.get('used_context'))._compute_report_balance_department(child_reports, data)
            departments = self._get_department_month(data)
        else:
            res = self.with_context(data.get('used_context'))._compute_report_balance_pl(child_reports, data)
            months = getMonthsInRange(start_date, end_date)

        for report in child_reports:
            # ratio_dict = dict({})
            vals = {
                'rec_id': report.id,
                'name': report.name,
                'code': report.sequence,
                'type': 'report',
                'parent_id': False,
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type or False,  # used to underline the financial report balances
                'account_view_type': '',
                'account_level': '',
            }
            if vals['code'] == 0:
                vals['code'] = ''
            if vals['level'] == 1 and report.parent_id:
                vals['parent_id'] = report.parent_id.id

            if data['report_type'] == 'ytd_pl_by_outlet':
                total = 0.0
                for outlet in outlets:
                    total += res[report.id][outlet]['balance'] * report.sign
                    vals[outlet] = res[report.id][outlet]['balance'] * report.sign
                vals['total'] = total
            elif data['report_type'] == 'pl_by_department_month':
                total = 0.0
                for department in departments:
                    total += res[report.id][department]['balance'] * report.sign
                    vals[department] = res[report.id][department]['balance'] * report.sign
                vals['total'] = total
            else:
                total = 0.0
                for month in months:
                    total += res[report.id][month]['balance'] * report.sign
                    vals[month] = res[report.id][month]['balance'] * report.sign
                vals['total'] = total
                # vals[date + '- Ratio %'] = 0.0
            lines.append(vals)
            if report.display_detail == 'no_detail':
                #  the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue
            if res[report.id].get('account'):
                sub_lines = []
                for account_id, value in res[report.id]['account'].items():
                    #  if there are accounts to display, we add them to the lines with a level equals to their level in
                    #  the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                    #  financial reports for Assets, liabilities...)
                    account = self.env['account.account'].browse(account_id)
                    account_view_type = False
                    if account.type and account.type == 'view':
                        account_view_type = 'View'
                    if account.type and account.type == 'other':
                        account_view_type = 'Regular'
                    vals = {
                        'name': account.name,
                        'code': account.code,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and 4,
                        'account_type': account.internal_type,
                        'account_view_type': account_view_type,
                        'account_level': account.level,
                    }

                    if data['report_type'] == 'ytd_pl_by_outlet':
                        total = 0.0
                        for outlet in self._get_outlet():
                            vals[outlet] = value[outlet]['balance'] * report.sign
                            total += value[outlet]['balance'] * report.sign
                        vals.update({'total': total})
                        # if total != 0.0:
                        sub_lines.append(vals)
                    elif data['report_type'] == 'pl_by_department_month':
                        total = 0.0
                        for department in self._get_department_month(data):
                            vals[department] = value[department]['balance'] * report.sign
                            total += value[department]['balance'] * report.sign
                        vals.update({'total': total})
                        # if total != 0.0:
                        sub_lines.append(vals)
                    else:
                        total = 0.0
                        for month in months:
                            vals[month] = value[month]['balance']* report.sign
                            total += value[month]['balance']* report.sign
                        vals.update({'total': total})
                        # if total != 0.0:
                        sub_lines.append(vals)
                lines += sorted(sub_lines, key=lambda sub_line: sub_line['name'])
        return lines

    @api.multi
    def action_print(self):
        BrOutlet = self.env['br_multi_outlet.outlet']
        data = self.check_report()
        if data.get('data'):
            data['data']['form'].update(self.read([
                'date_from_cmp', 'debit_credit', 'date_to_cmp',
                'filter_cmp', 'account_report_id', 'enable_filter',
                'label_filter', 'target_move', 'report_type', 'outlet_id', 'account_analytic_ids'])[0])
            for field in ['account_report_id']:
                if isinstance(data['data']['form'][field], tuple):
                    data['data']['form'][field] = data['data']['form'][field][0]
            for field in ['outlet_id']:
                if isinstance(data['data']['form'][field], tuple):
                    data['data']['form'][field] = data['data']['form'][field][0]

        date_from = data['data']['form']['date_from']
        date_to = data['data']['form']['date_to']
        # chk_date_from = datetime.strptime(date_from, '%Y-%m-%d')
        # chk_date_to = datetime.strptime(date_to, '%Y-%m-%d')
        if date_from > date_to:
            raise ValidationError(_('Please enter date from bigger then date to!!!!'))

        report_lines = self.get_account_lines_pl(data['data']['form'])
        fl = StringIO()
        workbook = xlsxwriter.Workbook(fl)
        if data['data']['form']['report_type'] == 'pl_by_outlet_month':
            worksheet = workbook.add_worksheet('P&L By outlet by month')
        elif data['data']['form']['report_type'] == 'pl_by_department_month':
            worksheet = workbook.add_worksheet('P&L By Department by month')
        elif data['data']['form']['report_type'] == 'ytd_pl_by_outlet':
            worksheet = workbook.add_worksheet('YTD P&L By Outlet')
        else:
            worksheet = workbook.add_worksheet('P&L By Month')
        # label_style = xlwt.easyxf('font: name Calibri;' 'align: horiz left;')
        label_style = workbook.add_format({
            'text_wrap': 1,
            'valign': 'vjustify',
        })
        label_style.set_font_name('Calibri')

        # amount_style = xlwt.easyxf('font: name Calibri;' 'align: horiz right;')
        amount_style = workbook.add_format({
            'valign': 'vjustify',
            'align': 'right',
            'font_name': 'Calibri'
        })

        # name_style = xlwt.easyxf('font: name Calibri;' 'align: horiz left;')
        name_style = workbook.add_format({
            'valign': 'vjustify',
            'font_name': 'Calibri',
            'align': 'left',
        })

        # style = xlwt.easyxf('font: name Calibri, bold on;' 'align: horiz center')
        style = workbook.add_format({
            'valign': 'vjustify',
            'bold': True,
            'align': 'center',
            'font_name': 'Calibri',
        })
        # header_style = xlwt.easyxf('font: name Calibri, bold on;')
        header_style = workbook.add_format({
            'valign': 'vjustify',
            'bold': True,
            'font_name': 'Calibri',
        })

        month_ratio_list = []
        if data['data']['form']['report_type'] in ['ytd_pl_by_outlet','pl_by_department_month']:
            outlets = []
            for line in report_lines:
                for key in line:
                    if key not in ['parent_id', 'level', 'code', 'name', 'rec_id', 'total', 'type', 'account_type','account_view_type','account_level'] and line[key] != 0.0:
                        outlets.append(key)
            month_ratio_list = list(set(outlets))
        else:
            month_ratio_list = getMonthsInRange(date_from, date_to)

        #  Headers
        # worksheet.col(0).width = 6000
        worksheet.set_column(0, 0, 50)
        if data['data']['form']['report_type'] in ('ytd_pl_by_outlet', 'pl_by_outlet_month','pl_by_department_month'):
            if data['data']['form']['report_type'] in ['ytd_pl_by_outlet','pl_by_department_month']:
                header_str = 'GSSB Outlet YTD P&L'
                if data['data']['form']['report_type'] == 'pl_by_department_month':
                    header_str = 'GSSB P&L By Department By Month '
                worksheet.merge_range('A1:B1', header_str, header_style)
                worksheet.set_column(1, 0, 15)
                worksheet.write(2, 0, 'Company: ', header_style)
                worksheet.set_column(1, 1, 15)
                worksheet.write(2, 1, self.env.user.company_id.name, header_style)
                worksheet.set_column(1, 2, 15)
                worksheet.write(2, 2, 'From Date:', header_style)
                worksheet.set_column(1, 3, 15)
                worksheet.write(2, 3, date_from, header_style)
                worksheet.set_column(1, 4, 15)
                worksheet.write(3, 2, 'To Date:', header_style)
                worksheet.set_column(1, 5, 15)
                worksheet.write(3, 3, date_to, header_style)
                # worksheet.merge_range()
            elif data['data']['form']['report_type'] == 'pl_by_outlet_month':
                outlet_str = ''
                if data['data']['form'].get('outlet_id'):
                    outlet = BrOutlet.browse(data['data']['form']['outlet_id'])
                    outlet_str = outlet.name
                worksheet.merge_range('A1:B1', 'GSSB Outlet Monthly P&L', header_style)
                worksheet.merge_range('A2:B2', 'OutLet: ' + outlet_str, header_style)
                # worksheet.write_merge(2, 2, 0, 1, 'Company: ' + self.env.user.company_id.name, header_style)
                worksheet.set_column(2, 0, 15)
                worksheet.write(2, 0, 'Company: ', header_style)
                worksheet.set_column(2, 1, 15)
                worksheet.write(2, 1, self.env.user.company_id.name, header_style)

                worksheet.set_column(2, 2, 15)
                worksheet.write(2, 2, 'From Date:', header_style)
                worksheet.set_column(3, 3, 15)
                worksheet.write(2, 3, date_from, header_style)
                worksheet.set_column(4, 4, 15)
                worksheet.write(3, 2, 'To Date:', header_style)
                worksheet.set_column(5, 5, 15)
                worksheet.write(3, 3, date_to, header_style)

            
            if data['data']['form']['report_type'] in ['pl_by_department_month','ytd_pl_by_outlet']:
                m_col = 5
                worksheet.set_column(5, 0, 25)
                worksheet.write(5, 0, 'Account Type', style)
                worksheet.write(5, 1, 'Account Level', style)
                worksheet.write(5, 2, 'Code', style)
                worksheet.write(5, 3, 'Level', style)
                # worksheet.set_column(4, 1, 15)
                worksheet.write(5, 4, 'Total', style)
                # worksheet.set_column(4, 1, 15)
                # worksheet.write(4, 2, '', style)
            else:
                m_col = 4
                worksheet.set_column(5, 0, 25)
                worksheet.write(5, 0, 'Account Type', style)
                worksheet.write(5, 1, 'Account Level', style)
                worksheet.write(5, 2, 'Level', style)
                # worksheet.set_column(4, 1, 15)
                worksheet.write(5, 3, 'Total', style)
                # worksheet.set_column(4, 1, 15)
                # worksheet.write(4, 2, '', style)
            
            if data['data']['form']['report_type'] in ['pl_by_department_month']:
                for month in sorted(month_ratio_list):
                    worksheet.write(4, m_col, month.split(' ')[0][:7], style)
                    worksheet.write(5, m_col, month[8:], style)
                    m_col += 1
            else:
                for month in sorted(month_ratio_list):
                    worksheet.write(5, m_col, month, style)
                    m_col += 1
        else:
            worksheet.merge_range('A1:B1', 'GSSB Retail Monthly P&L', header_style)
            # worksheet.write_merge(1, 1, 0, 1, 'Company: ' + self.env.user.company_id.name, header_style)
            worksheet.write(2, 0, 'Company: ', header_style)
            worksheet.write(2, 1, self.env.user.company_id.name, header_style)

            worksheet.set_column(2, 2, 15)
            worksheet.write(2, 2, 'From Date:', header_style)
            worksheet.set_column(3, 3, 15)
            worksheet.write(2, 3, date_from, header_style)
            worksheet.set_column(4, 4, 15)
            worksheet.write(3, 3, 'To Date:', header_style)
            # worksheet.set_column(5, 5, 15)
            worksheet.write(3, 3, date_to, header_style)

            worksheet.set_column(0, 0, 25)
            worksheet.write(5, 0, 'Account Type', style)
            worksheet.write(5, 1, 'Account Level', style)
            worksheet.write(5, 2, 'Code', style)
            worksheet.write(5, 3, 'Level', style)
            worksheet.write(5, 4, 'Total', style)
            # worksheet.write(4, 3, '', style)
            m_col = 5
            for month in sorted(month_ratio_list):
                worksheet.write(5, m_col, month, style)
                m_col += 1
        row = 6
        col = 0
        for line in report_lines:
            if line.get('level') != 0:
                if line.get('level') == 1:
                    worksheet.write(row, col, line['account_view_type'], name_style)
                    col = col + 1
                    worksheet.write(row, col, line['account_level'], name_style)
                    col = col + 1
                    if data['data']['form']['report_type'] in ['pl_by_month','pl_by_department_month','ytd_pl_by_outlet']:
                        col = col + 1
                    # worksheet.col(col).width = 8000
                    # worksheet.set_column(col, col, 2000)
                    worksheet.set_column(col, col, 50)
                    worksheet.write(row, col, line['name'], name_style)
                    col = col + 1
                    worksheet.write(row, col, line['total'], amount_style)
                    # col = col + 1
                    # worksheet.write(row, col, 0.0, amount_style)
                elif not line.get('level') > 3:
                    worksheet.write(row, col, line['account_view_type'], name_style)
                    col = col + 1
                    worksheet.write(row, col, line['account_level'], name_style)
                    col = col + 1
                    if data['data']['form']['report_type'] in ['pl_by_month','pl_by_department_month','ytd_pl_by_outlet']:
                        worksheet.write(row, col, line['code'], name_style)
                        col = col + 1
                    # worksheet.col(col).width = 8000
                    worksheet.set_column(col, col, 50)
                    worksheet.write(row, col, line['name'], name_style)
                    col = col + 1
                    worksheet.write(row, col, line['total'], amount_style)
                    # col = col + 1
                    # worksheet.write(row, col, 0.0, amount_style)
                else:
                    worksheet.write(row, col, line['account_view_type'], name_style)
                    col = col + 1
                    worksheet.write(row, col, line['account_level'], name_style)
                    col = col + 1
                    if data['data']['form']['report_type'] in ['pl_by_month','pl_by_department_month','ytd_pl_by_outlet']:
                        worksheet.write(row, col, line['code'], name_style)
                        col = col + 1
                    # worksheet.col(col).width = 8000
                    # worksheet.set_column(col, col, 8000)
                    worksheet.set_column(col, col, 50)
                    worksheet.write(row, col, line['name'], name_style)
                    col = col + 1
                    worksheet.write(row, col, line['total'], amount_style)
                    # col = col + 1
                    # worksheet.write(row, col, 0.0, amount_style)

                # if data['data']['form']['report_type'] == 'ytd_pl_by_outlet':
                #     for outlet in month_ratio_list:
                #         col += 1
                #         worksheet.write(row, col, abs(line[outlet]), amount_style)
                # else:
                for month in sorted(month_ratio_list):
                    col += 1
                    worksheet.write(row, col, line[month], amount_style)
                row += 1
                col = 0
        # workbook.save(fl)
        workbook.close()
        # fl.seek(0)
        # buf = base64.encodestring(fl.read())
        buf = base64.b64encode(fl.getvalue())
        fl.close()
        filename = "PL"
        self.write({'file': buf, 'name': filename})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=accounting.report&field=file&id=%s&filename=%s.xls' % (self.id, filename),
            'target': 'self',
        }
