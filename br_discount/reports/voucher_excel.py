from openerp import fields, models, api, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from datetime import datetime
import pytz


class baskin_voucher_excel_status(models.Model):
    _name = 'baskin.voucher.excel.status'

    name = fields.Char('Status')


class baskin_voucher_excel(models.TransientModel):
    _name = 'baskin.voucher.excel'

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    promotion_name = fields.Many2many('br.bundle.promotion', string='Discount Name')
    status = fields.Many2many('baskin.voucher.excel.status', string='Status')

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'baskin_voucher_excel.baskin_voucher_excel_report')


class baskin_voucher_excel_report(ReportXlsx):
    _name = 'report.baskin_voucher_excel.baskin_voucher_excel_report'

    def view_validation_code_access(self):
        if self.env.user.has_group('br_discount.group_voucher_view_validation'):
            return True
        return False

    def generate_xlsx_report(self, wb, data, report):
        ws = wb.add_worksheet('data')
        ws.set_column(0, 18, 25)
        font = 'Times New Roman'
        format_header = wb.add_format({
            'bold': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': font,
            'font_size': 12,
        })
        format_normal = wb.add_format({
            'bold': 0,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': font,
            'font_size': 12,
        })

        format_date = wb.add_format({
            'bold': 0,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': font,
            'font_size': 12,
            'num_format': 'dd/mm/yyyy',
        })

        if not report.end_date:
            sql_end_date_query = '1=1'
        else:
            sql_end_date_query = 'end_date <= ' + "\'{0}\'".format(report.end_date)

        voucher_status = []
        for status in report.status:
            voucher_status.append("\'{0}\'".format(status.name.lower()))

        if not voucher_status:
            sql_status_query = '1=1'
        else:
            v_status = ','.join(voucher_status)
            sql_status_query = 'status in (' + v_status + ')'

        promotions_name = []
        for promotion in report.promotion_name:
            promotions_name.append("\'{0}\'".format(promotion.real_name))

        if not promotions_name:
            sql_promotion_query = '1=1'
        else:
            promotion = ','.join(promotions_name)
            sql_promotion_query = 'promotion_name in (' + promotion + ')'


        arguments = {
            'start_date': report.start_date,
            'sql_end_date_query': sql_end_date_query,
            'sql_status_query': sql_status_query,
            'sql_promotion_query': sql_promotion_query
        }
        col = 0
        row = 0
        ws.write(row, col, u'Code', format_header)
        col += 1
        ws.write(row, col, u'Discount Name', format_header)
        col += 1
        ws.write(row, col, u'Voucher Code', format_header)
        col += 1
        if self.view_validation_code_access():
            ws.write(row, col, u'Voucher Validation Code', format_header)
            col += 1
        ws.write(row, col, u'Customer', format_header)
        col += 1
        ws.write(row, col, u'Start Date', format_header)
        col += 1
        ws.write(row, col, u'End Date', format_header)
        col += 1
        ws.write(row, col, u'Date Redeemed', format_header)
        col += 1
        ws.write(row, col, u'Status', format_header)
        col += 1
        ws.write(row, col, u'Pos Order', format_header)
        col += 1
        ws.write(row, col, u'Outlet Name', format_header)
        col += 1
        ws.write(row, col, u'Approval No', format_header)
        col += 1
        ws.write(row, col, u'Remarks', format_header)
        col += 1
        ws.write(row, col, u'Create Date', format_header)
        col += 1
        ws.write(row, col, u'Created By', format_header)
        col += 1
        ws.write(row, col, u'Third Party', format_header)
        col += 1
        ws.write(row, col, u'Member', format_header)
        col += 1
        ws.write(row, col, u'Free Coupon', format_header)
        col += 1
        ws.write(row, col, u'Flexible End Date', format_header)
        col += 1
        ws.write(row, col, u'Validity(in Days)', format_header)
        col += 1
        ws.write(row, col, u'Voucher Being Shared', format_header)

        row = 1
        vouchers = self.get_voucher_data(arguments)
        for voucher in vouchers:
            col = 0
            ws.write(row, col, voucher['p_code'], format_normal)
            col += 1
            ws.write(row, col, voucher['p_name'], format_normal)
            col += 1
            ws.write(row, col, voucher['vo_code'], format_normal)
            col += 1
            if self.view_validation_code_access():
                ws.write(row, col, voucher['va_code'], format_normal)
                col += 1
            ws.write(row, col, voucher['partner'], format_normal)
            col += 1
            ws.write(row, col, voucher['start_date'], format_date)
            col += 1
            ws.write(row, col, voucher['end_date'], format_date)
            col += 1
            ws.write(row, col, voucher['date_red'], format_date)
            col += 1
            ws.write(row, col, voucher['status'], format_normal)
            col += 1
            ws.write(row, col, voucher['pos_order'], format_normal)
            col += 1
            ws.write(row, col, voucher['outlet_name'], format_normal)
            col += 1
            ws.write(row, col, voucher['approval_no'], format_normal)
            col += 1
            ws.write(row, col, voucher['remarks'], format_normal)
            col += 1
            ws.write(row, col, voucher['create_date'], format_normal)
            col += 1
            ws.write(row, col, voucher['c_uid'], format_date)
            col += 1
            ws.write(row, col, voucher['third_party_id'], format_normal)
            col += 1
            ws.write(row, col, voucher['member_id'], format_normal)
            col += 1
            ws.write(row, col, voucher['free_deal'], format_normal)
            col += 1
            ws.write(row, col, voucher['flexible_end_date'], format_normal)
            col += 1
            ws.write(row, col, voucher['validity_days'], format_normal)
            col += 1
            ws.write(row, col, voucher['shared_voucher'], format_normal)
            row += 1
        wb.close()

    def get_voucher_data(self, args):
        sql = '''
        SELECT
        promotion_code AS p_code,
        promotion_name AS p_name,
        voucher_code   AS vo_code,
        voucher_validation_code AS va_code,
        partner_id  AS partner,
        start_date,
        end_date,
        date_red,
        status,
        order_id AS pos_order,
        outlet_name,
        approval_no,
        remarks,
        date(c_date) AS create_date,
        c_uid,
        third_party_id,
        member_id,
        free_deal,
        flexible_end_date,
        validity_days,
        COALESCE(shared_voucher, false) AS shared_voucher
        FROM br_voucher_listing
        WHERE start_date >= '{start_date}'
        AND {sql_end_date_query}
        AND {sql_status_query}
        AND {sql_promotion_query}        
        '''.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

baskin_voucher_excel_report('report.baskin_voucher_excel.baskin_voucher_excel_report', 'baskin.voucher.excel')