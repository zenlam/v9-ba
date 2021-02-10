from openerp import fields, models, api, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from openerp.tools import float_is_zero
import time


class AccountAgedTrialBalance(models.TransientModel):
    _inherit = 'account.aged.trial.balance'

    partner_ids = fields.Many2many(comodel_name='res.partner', string='Partner(s)')

    def pre_print_report(self, data):
        super(AccountAgedTrialBalance, self).pre_print_report(data)
        data['form'].update(self.read(['partner_ids'])[0])
        return data

    def _print_report(self, data):
        res = super(AccountAgedTrialBalance, self)._print_report(data)
        if self.env.context.get('print_excel', False):
            return self._print_excel(data)
        return res

    def _print_excel(self, data):
        """
        Print account aged trial balance report in excel format
        :param data:
        :return:
        """
        context = self.env.context.copy()
        context.update(data=data)
        return self.env['report'].with_context(context).get_action(self, 'baskin_partner_aged_advance_report.report_agedpartnerbalance_excel')


class ReportAgedPartnerBalance(models.AbstractModel):
    _inherit = 'report.account.report_agedpartnerbalance'

    def _get_partner_move_lines(self, form, account_type, date_from, target_move):
        res = []
        self.total_account = []
        cr = self.env.cr
        user_company = self.env.user.company_id.id
        move_state = ['draft', 'posted']
        if target_move == 'posted':
            move_state = ['posted']
        arg_list = (tuple(move_state), tuple(account_type))
        # build the reconciliation clause to see what partner needs to be printed
        reconciliation_clause = '(l.reconciled IS FALSE)'
        cr.execute('SELECT debit_move_id, credit_move_id FROM account_partial_reconcile where create_date > %s', (date_from,))
        reconciled_after_date = []
        for row in cr.fetchall():
            reconciled_after_date += [row[0], row[1]]
        if reconciled_after_date:
            reconciliation_clause = '(l.reconciled IS FALSE OR l.id IN %s)'
            arg_list += (tuple(reconciled_after_date),)
        arg_list += (date_from, user_company)

        query = '''
            SELECT DISTINCT res_partner.id AS id, res_partner.name AS name, UPPER(res_partner.name) AS uppername
            FROM res_partner,account_move_line AS l, account_account, account_move am
            WHERE (l.account_id = account_account.id)
                AND (l.move_id = am.id)
                AND (am.state IN %s)
                AND (account_account.internal_type IN %s)
                AND ''' + reconciliation_clause + '''
                AND (l.partner_id = res_partner.id)
                AND (l.date <= %s)
                AND l.company_id = %s
            ORDER BY UPPER(res_partner.name)'''
        cr.execute(query, arg_list)

        partners = cr.dictfetchall()
        # put a total of 0
        for i in range(7):
            self.total_account.append(0)

        # Build a string like (1,2,3) for easy use in SQL query
        partner_ids = [partner['id'] for partner in partners]
        if 'partner_ids' in form and form['partner_ids']:
            partner_ids = [x for x in partner_ids if x in form['partner_ids']]

        if not partner_ids:
            return []

        # This dictionary will store the not due amount of all partners
        future_past = {}
        query = '''SELECT l.id
                FROM account_move_line AS l, account_account, account_move am
                WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                    AND (am.state IN %s)
                    AND (account_account.internal_type IN %s)
                    AND (COALESCE(l.date_maturity,l.date) > %s)\
                    AND (l.partner_id IN %s)
                AND (l.date <= %s)
                AND l.company_id = %s'''
        cr.execute(query, (tuple(move_state), tuple(account_type), date_from, tuple(partner_ids), date_from, user_company))
        aml_ids = cr.fetchall()
        aml_ids = aml_ids and [x[0] for x in aml_ids] or []
        for line in self.env['account.move.line'].browse(aml_ids):
            if line.partner_id.id not in future_past:
                future_past[line.partner_id.id] = 0.0
            line_amount = line.balance
            if line.balance == 0:
                continue
            for partial_line in line.matched_debit_ids:
                if partial_line.create_date[:10] <= date_from:
                    line_amount += partial_line.amount
            for partial_line in line.matched_credit_ids:
                if partial_line.create_date[:10] <= date_from:
                    line_amount -= partial_line.amount
            future_past[line.partner_id.id] += line_amount

        # Use one query per period and store results in history (a list variable)
        # Each history will contain: history[1] = {'<partner_id>': <partner_debit-credit>}
        history = []
        for i in range(5):
            args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            dates_query = '(COALESCE(l.date_maturity,l.date)'

            if form[str(i)]['start'] and form[str(i)]['stop']:
                dates_query += ' BETWEEN %s AND %s)'
                args_list += (form[str(i)]['start'], form[str(i)]['stop'])
            elif form[str(i)]['start']:
                dates_query += ' >= %s)'
                args_list += (form[str(i)]['start'],)
            else:
                dates_query += ' <= %s)'
                args_list += (form[str(i)]['stop'],)
            args_list += (date_from, user_company)

            query = '''SELECT l.id
                    FROM account_move_line AS l, account_account, account_move am
                    WHERE (l.account_id = account_account.id) AND (l.move_id = am.id)
                        AND (am.state IN %s)
                        AND (account_account.internal_type IN %s)
                        AND (l.partner_id IN %s)
                        AND ''' + dates_query + '''
                    AND (l.date <= %s)
                    AND l.company_id = %s'''
            cr.execute(query, args_list)
            partners_amount = {}
            aml_ids = cr.fetchall()
            aml_ids = aml_ids and [x[0] for x in aml_ids] or []
            for line in self.env['account.move.line'].browse(aml_ids):
                if line.partner_id.id not in partners_amount:
                    partners_amount[line.partner_id.id] = 0.0
                line_amount = line.balance
                if line.balance == 0:
                    continue
                for partial_line in line.matched_debit_ids:
                    if partial_line.create_date[:10] <= date_from:
                        line_amount += partial_line.amount
                for partial_line in line.matched_credit_ids:
                    if partial_line.create_date[:10] <= date_from:
                        line_amount -= partial_line.amount

                partners_amount[line.partner_id.id] += line_amount
            history.append(partners_amount)

        for partner in partners:
            at_least_one_amount = False
            values = {}
            # Query here is replaced by one query which gets the all the partners their 'after' value
            after = False
            if partner['id'] in future_past:  # Making sure this partner actually was found by the query
                after = [future_past[partner['id']]]

            self.total_account[6] = self.total_account[6] + (after and after[0] or 0.0)
            values['direction'] = after and after[0] or 0.0
            if not float_is_zero(values['direction'], precision_rounding=self.env.user.company_id.currency_id.rounding):
                at_least_one_amount = True

            for i in range(5):
                during = False
                if partner['id'] in history[i]:
                    during = [history[i][partner['id']]]
                # Adding counter
                self.total_account[(i)] = self.total_account[(i)] + (during and during[0] or 0)
                values[str(i)] = during and during[0] or 0.0
                if not float_is_zero(values[str(i)], precision_rounding=self.env.user.company_id.currency_id.rounding):
                    at_least_one_amount = True
            values['total'] = sum([values['direction']] + [values[str(i)] for i in range(5)])
            ## Add for total
            self.total_account[(i + 1)] += values['total']
            values['name'] = partner['name']

            if at_least_one_amount:
                res.append(values)

        total = 0.0
        totals = {}
        for r in res:
            total += float(r['total'] or 0.0)
            for i in range(5) + ['direction']:
                totals.setdefault(str(i), 0.0)
                totals[str(i)] += float(r[str(i)] or 0.0)
        return res


class BRReportAccountAgedTrialBalanceExcel(ReportXlsx):
    _name = 'report.baskin_partner_aged_advance_report.report_agedpartnerbalance_excel'
    _description = 'Account Aged Trial balance Report Excel'
    formats = {}

    def set_formats(self, wb):
        # DEFINE FORMATS
        self.formats.update(
            bold_right_big=wb.add_format({
                'bold': 1,
                'text_wrap': 1,
                'align': 'right',
                'valign': 'vcenter',
                'font_name': 'Times New Roman',
                'font_size': 20
            }),
            bold_left_big=wb.add_format({
                'bold': 1,
                'text_wrap': 1,
                'align': 'left',
                'valign': 'vcenter',
                'font_name': 'Times New Roman',
                'font_size': 20

            }),
            bold=wb.add_format({
                'bold': 1,
                'text_wrap': 1,
                'valign': 'vcenter',
                'font_name': 'Times New Roman'
            }),
            right=wb.add_format({
                'text_wrap': 1,
                'align': 'right',
                'valign': 'vcenter',
                'num_format': '#,##0.00',
                'font_name': 'Times New Roman'
            }),
            left=wb.add_format({
                'text_wrap': 1,
                'align': 'left',
                'valign': 'vcenter',
                'num_format': '#,##0.00',
                'font_name': 'Times New Roman'
            }),
            center=wb.add_format({
                'text_wrap': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_name': 'Times New Roman'
            }),
            table_header=wb.add_format({
                'bold': 1,
                'text_wrap': 1,
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'num_format': '#,##0.00',
                'font_name': 'Times New Roman',
            }),

            table_header_right=wb.add_format({
                'bold': 1,
                'text_wrap': 1,
                'align': 'right',
                'valign': 'vcenter',
                'border': 1,
                'num_format': '#,##0.00',
                'font_name': 'Times New Roman',
            }),
            table_row_left=wb.add_format({
                'text_wrap': 1,
                'align': 'left',
                'valign': 'vcenter',
                'border': 1,
                'font_name': 'Times New Roman',
            }),

            table_row_right=wb.add_format({
                'text_wrap': 1,
                'align': 'right',
                'valign': 'vcenter',
                'border': 1,
                'num_format': '#,##0.00',
                'font_name': 'Times New Roman',
            }),

            table_row_date=wb.add_format({
                'text_wrap': 1,
                'align': 'left',
                'valign': 'vcenter',
                'border': 1,
                'font_name': 'Times New Roman',
                'num_format': 'dd/mm/yyyy',
            }),

            cell_date=wb.add_format({
                'text_wrap': 1,
                'align': 'left',
                'valign': 'vcenter',
                'font_name': 'Times New Roman',
                'num_format': 'dd/mm/yyyy',
            }),

            table_row_time=wb.add_format({
                'text_wrap': 1,
                'align': 'left',
                'valign': 'vcenter',
                'border': 1,
                'font_name': 'Times New Roman',
                'num_format': 'hh:mm:ss',
            }),

            table_row_datetime=wb.add_format({
                'text_wrap': 1,
                'align': 'left',
                'valign': 'vcenter',
                'border': 1,
                'font_name': 'Times New Roman',
                'num_format': 'dd/mm/yyyy hh:mm:ss',
            })
        )

    def set_paper(self, wb, ws):
        # SET PAPERS
        wb.formats[0].font_name = 'Times New Roman'
        wb.formats[0].font_size = 11
        ws.set_paper(9)
        ws.center_horizontally()
        ws.set_margins(left=0.28, right=0.28, top=0.5, bottom=0.5)
        ws.fit_to_pages(1, 0)
        ws.set_landscape()
        ws.fit_to_pages(1, 1)

    def set_header(self, ws, data):
        # Report Header
        ws.merge_range('A1:B1', "Aged Trial Balance", self.formats['bold_left_big'])

        ws.write('A3', 'Start Date', self.formats['bold'])
        ws.write('A4', data['date_from'], self.formats['left'])

        ws.write('C3', 'Period Length (days)', self.formats['bold'])
        ws.write('C4', data['period_length'], self.formats['left'])

        ws.write('A6', "Partner's", self.formats['bold'])
        ws.write('A7', data['result_selection'] == 'customer' and 'Receivable Accounts'
                 or data['result_selection'] == 'supplier' and 'Payable Accounts'
                 or data['result_selection'] == 'customer_supplier' and 'Receivable and Payable Accounts'
                 or '', self.formats['left'])

        ws.write('C6', "Target Moves:", self.formats['bold'])
        ws.write('C7', data['target_move'] == 'all' and 'All Entries' or data['target_move'] == 'posted' and 'All Posted Entries' and '')

    def generate_xlsx_report(self, wb, data, report):
        """
        Generate report in excel format by micmic pdf report
        :param wb:
        :param data:
        :param report:
        :return:
        """

        # Prepare data

        data = self.env.context.get('data', data)

        target_move = data['form'].get('target_move', 'all')
        date_from = data['form'].get('date_from', time.strftime('%Y-%m-%d'))

        if data['form']['result_selection'] == 'customer':
            account_type = ['receivable']
        elif data['form']['result_selection'] == 'supplier':
            account_type = ['payable']
        else:
            account_type = ['payable', 'receivable']

        report_balance = self.env['report.account.report_agedpartnerbalance'].new()
        report_balance.total_account = []
        without_partner_movelines = report_balance._get_move_lines_with_out_partner(data['form'], account_type, date_from, target_move)
        tot_list = report_balance.total_account
        partner_movelines = report_balance._get_partner_move_lines(data['form'], account_type, date_from, target_move)

        for i in range(7):
            report_balance.total_account[i] += tot_list[i]
        movelines = partner_movelines + without_partner_movelines

        # Map original function variable with new variable
        data = data['form']
        get_direction = report_balance.total_account
        get_partner_lines = movelines

        # Worksheet
        ws = wb.add_worksheet('Aged Trial Balance Report')

        # Add cell formats
        self.set_formats(wb)

        # Set paper format
        self.set_paper(wb, ws)

        # Set report header
        self.set_header(ws, data)

        # Set column width
        ws.set_column(0, 7, 25)

        #####################################################
        #                   Table Header                    #
        #####################################################
        ROW = 9

        ws.write('A%s' % ROW, 'Partners', self.formats['table_header'])
        ws.write('B%s' % ROW, 'Not due', self.formats['table_header'])
        ws.write('C%s' % ROW, data['4']['name'], self.formats['table_header'])
        ws.write('D%s' % ROW, data['3']['name'], self.formats['table_header'])
        ws.write('E%s' % ROW, data['2']['name'], self.formats['table_header'])
        ws.write('F%s' % ROW, data['1']['name'], self.formats['table_header'])
        ws.write('G%s' % ROW, data['0']['name'], self.formats['table_header'])
        ws.write('H%s' % ROW, 'Total', self.formats['table_header'])

        ROW += 1
        ws.write('A%s' % ROW, 'Account Total', self.formats['table_header'])
        ws.write('B%s' % ROW, get_direction[6], self.formats['table_header_right'])
        ws.write('C%s' % ROW, get_direction[4], self.formats['table_header_right'])
        ws.write('D%s' % ROW, get_direction[3], self.formats['table_header_right'])
        ws.write('E%s' % ROW, get_direction[2], self.formats['table_header_right'])
        ws.write('F%s' % ROW, get_direction[1], self.formats['table_header_right'])
        ws.write('G%s' % ROW, get_direction[0], self.formats['table_header_right'])
        ws.write('H%s' % ROW, get_direction[5], self.formats['table_header_right'])

        #####################################################
        #                  Table Body                       #
        #####################################################
        ROW += 1
        for partner in get_partner_lines:
            ws.write('A%s' % ROW, partner['name'], self.formats['table_row_left'])
            ws.write('B%s' % ROW, partner['direction'], self.formats['table_row_right'])
            ws.write('C%s' % ROW, partner['4'], self.formats['table_row_right'])
            ws.write('D%s' % ROW, partner['3'], self.formats['table_row_right'])
            ws.write('E%s' % ROW, partner['2'], self.formats['table_row_right'])
            ws.write('F%s' % ROW, partner['1'], self.formats['table_row_right'])
            ws.write('G%s' % ROW, partner['0'], self.formats['table_row_right'])
            ws.write('H%s' % ROW, partner['total'], self.formats['table_row_right'])
            ROW += 1


BRReportAccountAgedTrialBalanceExcel('report.baskin_partner_aged_advance_report.report_agedpartnerbalance_excel', 'account.aged.trial.balance')
