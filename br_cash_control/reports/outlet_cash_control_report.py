# --*-- coding: utf-8 --*--

from openerp import fields, models, api, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
import pytz
from datetime import datetime

import time
import logging
_logger = logging.getLogger(__name__)

class outlet_cash_control_popup(models.TransientModel):
    _name = 'outlet.cash.control'

    start_date = fields.Date(string=_("Start date"))
    end_date = fields.Date(string=_("End date"))
    outlet_ids = fields.Many2many(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_cash_control.outlet_cash_control')


class outlet_cash_control_report(ReportXlsx):
    _name = 'report.br_cash_control.outlet_cash_control'

    @api.multi
    def render_html(self, data):
        pass

    def convert_timezone(self, from_tz, to_tz, date):
        from_tz = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone(from_tz))
        to_tz = from_tz.astimezone(pytz.timezone(to_tz))
        return to_tz.strftime("%Y-%m-%d %H:%M:%S")


    def generate_xlsx_report(self, wb, data, report):
        ws = wb.add_worksheet('data')

        # SET PAPERS
        wb.formats[0].font_name = 'Times New Roman'
        wb.formats[0].font_size = 11
        ws.set_paper(9)
        ws.center_horizontally()
        ws.set_margins(left=0.28, right=0.28, top=0.5, bottom=0.5)
        ws.fit_to_pages(1, 0)
        ws.set_landscape()
        ws.fit_to_pages(1, 1)

        # DEFINE FORMATS
        bold_right_big = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
        bold = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
        right = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman'
        })

        center = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
        table_header = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
        })

        table_row_left = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
        })

        table_row_right = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })

        table_row_datetime = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy hh:mm:ss'
        })

        table_row_date = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy'
        })

        # SET COLUMNS'S WIDTH
        ws.set_column(0, 100, 30)
        # ws.set_column(1, 1, 30)
        # ws.set_column(2, 2, 30)
        # ws.set_column(3, 3, 30)
        # ws.set_column(4, 4, 30)
        # ws.set_column(5, 5, 30)
        # ws.set_column(6, 6, 30)
        # ws.set_column(7, 7, 30)
        # ws.set_column(8, 8, 30)
        # ws.set_column(9, 9, 30)
        # ws.set_column(10, 10, 30)
        # ws.set_column(11, 11, 30)
        # ws.set_column(12, 12, 30)

        # REPORT'S HEADER
        utc_start_date = self.convert_timezone(self.env.user.tz or 'UTC', 'UTC', report.start_date + ' 00:00:00')
        utc_end_date = self.convert_timezone(self.env.user.tz or 'UTC', 'UTC', report.end_date + ' 23:59:59')
        outlets = report.outlet_ids
        if not outlets:
            outlets = self.env.user.outlet_ids
        search_credential = {
            'start_date': utc_start_date,
            'end_date': utc_end_date,
            'outlet_ids': ','.join([str(x.id) for x in outlets]) if len(outlets) > 0 else 'NULL',
            'company_id': self.env.user.company_id.id
        }
        # Create columns as many as available cash controls then fill total per cash control when binding data
        cash_control = self.env['br.cash.control'].search([('company_id', '=', self.env.user.company_id.id)], order='action, name')
        cash_control_names = []
        cash_control_ids = []
        for cc in cash_control:
            cash_control_names.append(cc.name)
            cash_control_ids.append(cc.id)
        cash_control_datas = self.get_cash_controls(search_credential)
        cash_controls = {}
        for x in cash_control_datas:
            cash_controls[(x['session_name'], x['cash_control_id'])] = abs(x['amount'])
        ws.write('A1', u'Start Date', bold)
        ws.write('A2', u'End Date', bold)
        ws.write('A3', u'Outlet(s)', bold)
        ws.write_datetime('B1', datetime.strptime(report.start_date, "%Y-%m-%d"), table_row_date)
        ws.write_datetime('B2', datetime.strptime(report.end_date, "%Y-%m-%d"), table_row_date)
        ws.write('B3', ', '.join([x.name for x in report.outlet_ids]))

        # ------------------- Header -------------------
        ws.write(4, 0, 'Outlet', table_header)
        ws.write(4, 1, 'Session No', table_header)
        ws.write(4, 2, 'Session Date', table_header)
        ws.write(4, 3, 'PIC', table_header)
        ws.write(4, 4, 'Opening Balance', table_header)
        ws.write(4, 5, 'Cash Collection Amount', table_header)
        col = 6
        for cc in cash_control_names:
            ws.write(4, col, cc, table_header)
            col += 1
        ws.write(4, col, 'Cash Difference', table_header)
        ws.write(4, col + 1, 'Theoretical Closing Balance', table_header)
        ws.write(4, col + 2, 'Actual Closing Balance', table_header)

        # FILL DATA
        report_data = self.get_report_data(search_credential)
        _logger.info(">>>>>> Starting to export cash control report (%s records)" % len(report_data))
        row = 5
        for line in report_data:
            ws.write(row, 0, line['outlet_name'], table_row_left)
            ws.write(row, 1, line['session_name'], table_row_left)
            start_at = self.convert_timezone('UTC', self.env.user.tz or 'UTC', line['start_at'])
            ws.write_datetime(row, 2, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
            ws.write(row, 3, line['pic'], table_row_left)
            ws.write(row, 4, line['opening_balance'], table_row_right)
            ws.write(row, 5, line['transaction_amount'], table_row_right)
            line_cash_control_ids = line['cash_control_ids'].split("|") if line['cash_control_ids'] else []
            line_col = 6
            for cid in cash_control_ids:
                ws.write(row, line_col, 0, table_row_right)
                for l_cid in line_cash_control_ids:
                    if cid == int(l_cid):
                        ws.write(row, line_col, cash_controls[(line['session_name'], int(cid))], table_row_right)
                        break
                line_col += 1
            ws.write(row, col, line['posted_cash_register_difference'] or line['cash_register_difference'], table_row_right)
            ws.write(row, col + 1, line['posted_cash_register_balance_end'] or line['cash_register_balance_end'], table_row_right)
            ws.write(row, col + 2, line['cash_register_balance_end_real'] or 0, table_row_right)
            row += 1

    def get_workbook_options(self):
        return {}

    def get_report_data(self, args):
        sql = """
        SELECT
          outlet.name                              AS outlet_name,
          ps.name                                  AS session_name,
          ps.start_at,
          rp.name                                  AS pic,
          MAX(abs.balance_start)                   AS opening_balance,
          SUM(CASE WHEN absl.pos_statement_id IS NOT NULL AND aj.type = 'cash'
            THEN absl.amount ELSE 0 END)
          +
          SUM(CASE WHEN absl.pos_statement_id IS NOT NULL AND aj.type = 'cash' and aj.is_rounding_method = True
            THEN absl.amount * -1  ELSE 0 END)   
          AS transaction_amount,
          string_agg(DISTINCT bcc.id :: TEXT, '|')          AS cash_control_ids,
          MAX(ps.posted_cash_register_difference)  AS posted_cash_register_difference,
          MAX(ps.posted_cash_register_balance_end) AS posted_cash_register_balance_end,
          MAX(abs.difference)                      AS cash_register_difference,
          MAX(abs.balance_end)                     AS cash_register_balance_end,
          MAX(COALESCE(abs.balance_end_real, 0))   AS cash_register_balance_end_real
        FROM pos_session ps
            INNER JOIN pos_config pc ON ps.config_id = pc.id
            LEFT JOIN br_multi_outlet_outlet outlet ON ps.outlet_id = outlet.id
            LEFT JOIN res_users ru ON ps.user_id = ru.id
            LEFT JOIN res_partner rp ON ru.partner_id = rp.id
            LEFT JOIN account_bank_statement abs ON ps.id = abs.pos_session_id
            INNER JOIN account_journal aj ON abs.journal_id = aj.id
            LEFT JOIN account_bank_statement_line absl ON abs.id = absl.statement_id
            LEFT JOIN br_cash_control bcc ON absl.cash_control_id = bcc.id
        WHERE ps.start_at >= '{start_date}'
            AND ps.start_at <= '{end_date}'
            AND pc.company_id = {company_id}
            AND CASE WHEN '{outlet_ids}' != 'NULL' THEN ps.outlet_id IN ({outlet_ids}) ELSE 1 = 1 END
            AND aj.type = 'cash'
        GROUP BY ps.id, outlet.id, rp.id
        ORDER BY outlet.name, ps.start_at
        """.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_cash_controls(self, args):
        sql = """
        SELECT
            ps.name  AS session_name,
            bcc.id AS cash_control_id,
            bcc.name AS cash_control_name,
            SUM(absl.amount) AS amount
        FROM pos_session ps
            INNER JOIN pos_config pc ON ps.config_id = pc.id
            LEFT JOIN br_multi_outlet_outlet outlet ON ps.outlet_id = outlet.id
            LEFT JOIN account_bank_statement abs ON ps.cash_register_id = abs.id
            INNER JOIN account_journal aj ON abs.journal_id = aj.id
            LEFT JOIN account_bank_statement_line absl ON abs.id = absl.statement_id
            INNER JOIN br_cash_control bcc ON absl.cash_control_id = bcc.id
        WHERE ps.start_at >= '{start_date}'
            AND ps.start_at <= '{end_date}'
            AND pc.company_id = {company_id}
            AND CASE WHEN '{outlet_ids}' != 'NULL' THEN ps.outlet_id IN ({outlet_ids}) ELSE 1 = 1 END
            AND aj.type = 'cash'
        GROUP BY ps.id, outlet.id, bcc.id
        ORDER BY bcc.action, bcc.name;
        """.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data


outlet_cash_control_report('report.br_cash_control.outlet_cash_control', 'outlet.cash.control')