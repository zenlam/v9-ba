from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp import http
from openerp.addons.web.controllers.main import serialize_exception, content_disposition
import StringIO
import xlsxwriter
from openerp.http import request


# TODO: Create report using report_xlsx class instead of Controller
class VoucherReport(http.Controller):
    @http.route('/web/binary/download_voucher', type='http', auth="public")
    @serialize_exception
    def download_voucher(self, model, id, **kw):
        obj_model = request.registry[model]
        cr, uid, context = request.cr, request.uid, request.context
        promotion = obj_model.browse(cr, uid, [int(id)], context)
        output = StringIO.StringIO()
        filename = '%s.xlsx' % promotion.real_name
        # Generate excel.
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Vouchers')
        # set format
        font = 'Palatino Linotype'
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

        format_datetime = wb.add_format({
            'bold': 0,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': font,
            'font_size': 12,
            'num_format': 'dd/mm/yyyy hh:mm:ss',
        })

        format_date = wb.add_format({
            'bold': 0,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': font,
            'font_size': 12,
            'num_format': 'dd/mm/yyyy',
        })
        # set column width
        ws.set_column('A:H', 18)

        # write header
        col = 0
        row = 0
        ws.write(row, col, 'Discount Name', format_header)
        col += 1
        ws.write(row, col, 'Voucher Code', format_header)
        col += 1
        if self.view_validation_code_access():
            ws.write(row, col, 'Voucher Validation Code', format_header)
            col += 1
        ws.write(row, col, 'Customer', format_header)
        col += 1
        ws.write(row, col, 'Start Date', format_header)
        col += 1
        ws.write(row, col, 'End Date', format_header)
        col += 1
        ws.write(row, col, 'Date Redeemed', format_header)
        col += 1
        ws.write(row, col, 'Status', format_header)
        col += 1
        ws.write(row, col, 'Pos Order', format_header)
        col += 1
        ws.write(row, col, 'Outlet Name', format_header)
        col += 1
        ws.write(row, col, 'Approval No', format_header)
        col += 1
        ws.write(row, col, 'Remarks', format_header)
        col += 1
        ws.write(row, col, 'Create Date', format_header)
        col += 1
        ws.write(row, col, 'Created by', format_header)
        col += 1

        # write voucher record
        row = 1
        vouchers = self.get_voucher_data(promotion)
        for voucher in vouchers:
            col = 0
            ws.write(row, col, voucher['promotion_name'], format_normal)
            col += 1
            ws.write(row, col, voucher['voucher_code'], format_normal)
            col += 1
            if self.view_validation_code_access():
                ws.write(row, col, voucher['voucher_validation_code'], format_normal)
                col += 1
            ws.write(row, col, voucher['partner_name'], format_normal)
            col += 1
            if voucher['start_date']:
                ws.write_datetime(row, col, datetime.strptime(voucher['start_date'], DEFAULT_SERVER_DATE_FORMAT), format_date)
                col += 1
            else:
                ws.write(row, col, "")
                col += 1
            if voucher['end_date']:
                ws.write_datetime(row, col, datetime.strptime(voucher['end_date'], DEFAULT_SERVER_DATE_FORMAT), format_date)
                col += 1
            else:
                ws.write(row, col, "")
                col += 1
            if voucher['date_red']:
                ws.write_datetime(row, col, datetime.strptime(voucher['date_red'], DEFAULT_SERVER_DATE_FORMAT), format_date)
                col += 1
            else:
                ws.write(row, col, "")
                col += 1
            ws.write(row, col, voucher['status'], format_normal)
            col += 1
            ws.write(row, col, voucher['order_name'], format_normal)
            col += 1
            ws.write(row, col, voucher['outlet_name'], format_normal)
            col += 1
            ws.write(row, col, voucher['approval_no'], format_normal)
            col += 1
            ws.write(row, col, voucher['remarks'], format_normal)
            col += 1
            ws.write(row, col, voucher['create_date'], format_normal)
            col += 1
            ws.write(row, col, voucher['c_uid'], format_normal)
            row += 1
        wb.close()

        # Construct response.
        output.seek(0)
        return request.make_response(output.read(),
                                     [('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                                      ('Content-Disposition', content_disposition(filename))])

    def view_validation_code_access(self):
        if http.request.env.user.has_group('br_discount.group_voucher_view_validation'):
            return True
        return False

    def get_voucher_data(self, promotion):
        query = """
        SELECT
          promotion.real_name AS promotion_name,
          voucher.approval_no,
          voucher.remarks,
          voucher.create_date,
          rp3.name AS c_uid,
          voucher.voucher_code,
          voucher.voucher_validation_code,
          CASE WHEN string_agg(rp2.name, ', ') IS NOT NULL THEN string_agg(rp2.name, ',') ELSE rp1.name END AS partner_name,
          voucher.start_date,
          voucher.end_date,
          voucher.date_red,
          voucher.status,
          pos_order.name as order_name,
          bmoo.name as outlet_name
        FROM br_config_voucher voucher
          LEFT JOIN pos_order ON voucher.order_id = pos_order.id
          LEFT JOIN res_partner rp1 ON voucher.partner_id = rp1.id
          LEFT JOIN res_partner rp2 ON rp1.id = rp2.parent_id
          LEFT JOIN res_users ru ON voucher.create_uid = ru.id
          LEFT JOIN res_partner rp3 ON ru.partner_id = rp3.id
          LEFT JOIN br_multi_outlet_outlet bmoo ON pos_order.outlet_id = bmoo.id
          LEFT JOIN br_bundle_promotion promotion ON voucher.promotion_id = promotion.id
        WHERE voucher.promotion_id = %s
        GROUP BY voucher.id, pos_order.id, rp1.id, bmoo.id, promotion.id, rp3.name
        ORDER BY voucher.voucher_code
        """ % promotion.id
        promotion._cr.execute(query)
        return promotion._cr.dictfetchall()
