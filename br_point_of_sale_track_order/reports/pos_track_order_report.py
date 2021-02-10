# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime, timedelta
import xlsxwriter
import base64
from cStringIO import StringIO

import logging

_logger = logging.getLogger(__name__)
CANCEL_METHODS = {
    'cancel': 'Cancel Receipt',
    'delete': 'Delete Menu Name',
    'destroy': 'Destroy Transaction',
    'card': 'Manual Credit Card',
    'back': 'Back Button'
}


class ReportStockList(models.TransientModel):
    _name = 'pos.track.order.report'

    area_ids = fields.Many2many(comodel_name="res.country.state", string="Area(s)")
    region_ids = fields.Many2many(comodel_name="br_multi_outlet.region_area", string="Region(s)")
    outlet_ids = fields.Many2many(comodel_name="br_multi_outlet.outlet", string="Outlet(s)")
    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)
    report_type = fields.Selection(selection=[('summary', 'Summary'), ('detailed', 'Detailed')], string="Report Type", default='summary')
    break_down_by = fields.Selection(selection=[('day', 'Day'), ('month', 'Month')], string="Break Down By", default='day')
    file_name = fields.Binary()

    def _get_details_data(self, args):
        sql = """
        SELECT
            outlet.name             AS outlet_name,
            region.name             AS region_name,
            area.name               AS area_name,
            p_region_manager.name   AS region_mng,
            p_area_manager.name     AS area_mng,
            p_pic.name              AS pic_name,
            p_cashier.name          AS cashier_name,
            date_trunc('minute', ptol.date_log::timestamp(0)) + INTERVAL '8 HOURS' AS date,
            pto.invoice_no,
            menu_name.name_template AS menu_name,
            ptol.reason              AS method,
            ptol.unit_price         AS unit_price,
            COUNT(*)                AS qty,
            ptol.remark
        FROM pos_track_order pto
            LEFT JOIN pos_track_order_line ptol ON pto.id = ptol.track_order_id
            LEFT JOIN product_product menu_name ON ptol.product_id = menu_name.id
            LEFT JOIN br_multi_outlet_outlet outlet ON pto.outlet_id = outlet.id
            LEFT JOIN br_multi_outlet_region_area region ON outlet.region_area_id = region.id
            LEFT JOIN res_country_state area ON outlet.state_id = area.id
            LEFT JOIN res_users pic ON pto.pos_user = pic.id
            LEFT JOIN res_partner p_pic ON pic.partner_id = p_pic.id
            LEFT JOIN res_users cashier ON ptol.cashier_id = cashier.id
            LEFT JOIN res_partner p_cashier ON cashier.partner_id = p_cashier.id
            LEFT JOIN res_users region_manager ON outlet.region_manager = region_manager.id
            LEFT JOIN res_partner p_region_manager ON region_manager.partner_id = p_region_manager.id
            LEFT JOIN res_users area_manager ON outlet.area_manager = area_manager.id
            LEFT JOIN res_partner p_area_manager ON area_manager.partner_id = p_area_manager.id
        WHERE
            CASE WHEN '{outlet_ids}' != 'null' THEN pto.outlet_id IN ({outlet_ids}) ELSE 1 = 1 END
            AND CASE WHEN '{region_ids}' != 'null' THEN region.id IN ({region_ids}) ELSE 1 = 1 END
            AND CASE WHEN '{area_ids}' != 'null' THEN area.id IN ({area_ids}) ELSE 1 = 1 END
            AND ptol.date_log BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY
            outlet.name,
            region.name,
            area.name,
            p_region_manager.name,
            p_area_manager.name,
            p_pic.name,
            p_cashier.name,
            date_trunc('minute', ptol.date_log::timestamp(0)),
            pto.invoice_no,
            menu_name.name_template,
            ptol.reason,
            ptol.unit_price,
            ptol.remark
        """.format(**args)
        self.env.cr.execute(sql)
        return self.env.cr.dictfetchall()

    def _get_summary_data(self, args):
        sql = """
        SELECT
            outlet.name AS outlet_name,
            region.name as region_name,
            area.name as area_name,
            p_pic.name AS pic_name,
            p_region_manager.name AS region_mng,
            p_area_manager.name AS area_mng,
            date_trunc('{break_down_by}', ptol.date_log::timestamp(0) + INTERVAL '8 hours') as order_date,
            count(DISTINCT pto.id) FILTER (WHERE ptol.reason = 'cancel') AS cancel_receipt,
            count(DISTINCT ptol.id) FILTER (WHERE ptol.reason = 'delete') AS delete_menu_name,
            count(DISTINCT pto.id) FILTER (WHERE ptol.reason = 'destroy') AS destroy_transaction,
            count(DISTINCT pto.id) FILTER (WHERE ptol.reason = 'card') AS manual_credit_card,
            count(DISTINCT ptol.id) FILTER (WHERE ptol.reason = 'back') AS back_button,
            SUM(CASE WHEN ptol.reason = 'cancel' THEN ptol.unit_price * ptol.quantity ELSE 0 END) AS total_cancel_receipt,
            SUM(CASE WHEN ptol.reason = 'delete' THEN ptol.unit_price * ptol.quantity ELSE 0 END) AS total_delete_menu_name,
            SUM(CASE WHEN ptol.reason = 'destroy' THEN ptol.unit_price * ptol.quantity ELSE 0 END) AS total_destroy_transaction,
            SUM(CASE WHEN ptol.reason = 'card' THEN ptol.unit_price * ptol.quantity ELSE 0 END) AS total_manual_credit_card,
            SUM(CASE WHEN ptol.reason = 'back' THEN ptol.unit_price * ptol.quantity ELSE 0 END) AS total_back_button
        FROM pos_track_order pto
            LEFT JOIN pos_track_order_line ptol ON pto.id = ptol.track_order_id
            LEFT JOIN br_multi_outlet_outlet outlet ON pto.outlet_id = outlet.id
            LEFT JOIN br_multi_outlet_region_area region ON outlet.region_area_id = region.id
            LEFT JOIN res_country_state area ON outlet.state_id = area.id
            LEFT JOIN res_users pic ON pto.pos_user = pic.id
            LEFT JOIN res_partner p_pic ON pic.partner_id = p_pic.id
            LEFT JOIN res_users region_manager ON outlet.region_manager = region_manager.id
            LEFT JOIN res_partner p_region_manager ON region_manager.partner_id = p_region_manager.id
            LEFT JOIN res_users area_manager ON outlet.area_manager = area_manager.id
            LEFT JOIN res_partner p_area_manager ON area_manager.partner_id = p_area_manager.id
        WHERE
            CASE WHEN '{outlet_ids}' != 'null' THEN pto.outlet_id IN ({outlet_ids}) ELSE 1 = 1 END
            AND CASE WHEN '{region_ids}' != 'null' THEN region.id IN ({region_ids}) ELSE 1 = 1 END
            AND CASE WHEN '{area_ids}' != 'null' THEN area.id IN ({area_ids}) ELSE 1 = 1 END
            AND ptol.date_log BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY outlet.id, region.id, area.id, p_pic.id, p_region_manager.id, p_area_manager.id, date_trunc('{break_down_by}', ptol.date_log::timestamp(0) + INTERVAL '8 hours');
        """.format(**args)
        self.env.cr.execute(sql)
        return self.env.cr.dictfetchall()

    @api.multi
    def xlsx_export(self):
        self.ensure_one()
        fp = StringIO()
        workbook = xlsxwriter.Workbook(fp)
        ######################################################################
        left_style = workbook.add_format(
            {'valign': 'vcenter', 'align': 'left'})
        left_style.set_font_name('Calibri')
        left_style.set_font_size('11')
        ######################################################################
        center_bold_style = workbook.add_format(
            {'bold': 1, 'valign': 'vcenter', 'align': 'center'})
        center_bold_style.set_font_name('Calibri')
        center_bold_style.set_font_size('16')
        ######################################################################
        header_style = workbook.add_format(
            {'bold': 1, 'valign': 'vcenter', 'align': 'center'})
        header_style.set_font_name('Calibri')
        header_style.set_font_size('11')
        header_style.set_text_wrap()
        header_style.set_border()
        ######################################################################
        line_style = workbook.add_format(
            {'valign': 'vcenter', 'align': 'left'})
        line_style.set_font_name('Calibri')
        line_style.set_font_size('11')
        line_style.set_border()
        ######################################################################
        date_style = workbook.add_format(
            {'valign': 'vcenter', 'align': 'left'})
        date_style.set_font_name('Calibri')
        date_style.set_font_size('11')
        date_style.set_text_wrap()
        date_style.set_num_format('dd/mm/yyyy')
        date_style.set_border()
        ######################################################################
        month_style = workbook.add_format(
            {'valign': 'vcenter', 'align': 'left'})
        month_style.set_font_name('Calibri')
        month_style.set_font_size('11')
        month_style.set_text_wrap()
        date_style.set_num_format('mm/yyyy')
        month_style.set_border()
        ######################################################################

        start_date = self.date_from
        end_date = self.date_to
        outlet_ids = self.outlet_ids
        area_ids = self.area_ids
        region_ids = self.region_ids

        if self.report_type == 'detailed':
            filename = 'Fidelity Report Detailed'
            worksheet = workbook.add_worksheet('Details')
        else:
            filename = 'Fidelity Report Summary'
            worksheet = workbook.add_worksheet('Summary')

        worksheet.set_paper(9)
        worksheet.set_landscape()
        worksheet.set_margins(0.5, 0.3, 0.5, 0.5)
        worksheet.set_column(0, 15, 30)

        # Area
        worksheet.write('A1', 'Area(s): ', left_style)
        worksheet.merge_range('B1:L1',
                              ", ".join([x.name for x in area_ids if x]),
                              left_style)
        # Region
        worksheet.write('A2', 'Region(s): ', left_style)
        worksheet.merge_range('B2:L2',
                              ", ".join([x.name for x in region_ids if x]),
                              left_style)
        # Outlet
        worksheet.write('A3', 'Outlet(s): ', left_style)
        worksheet.merge_range('B3:L3',
                              ", ".join([x.name for x in outlet_ids if x]),
                              left_style)
        # Start Date
        worksheet.write('A4', 'Start Date: ', left_style)
        worksheet.merge_range('B4:L4', start_date, left_style)
        # End Date
        worksheet.write('A5', 'End Date: ', left_style)
        worksheet.merge_range('B5:L5', end_date, left_style)

        start_date = (datetime.strptime(start_date + ' 00:00:00',
                                        DEFAULT_SERVER_DATETIME_FORMAT) - timedelta(
            hours=8)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        end_date = (datetime.strptime(end_date + ' 23:59:59',
                                      DEFAULT_SERVER_DATETIME_FORMAT) - timedelta(
            hours=8)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        credentials = {
            'outlet_ids': ", ".join([str(x.id) for x in outlet_ids if
                                     x]) if outlet_ids else 'null',
            'region_ids': ", ".join([str(x.id) for x in region_ids if
                                     x]) if region_ids else 'null',
            'area_ids': ", ".join(
                [str(x.id) for x in area_ids if x]) if area_ids else 'null',
            'start_date': start_date,
            'end_date': end_date,
            'break_down_by': self.break_down_by
        }
        if self.report_type == 'summary':
            # Summary Report
            worksheet.set_row(7, 45)
            worksheet.write('A6', 'Break Down By: ', left_style)
            worksheet.merge_range('B6:L6', self.break_down_by, left_style)
            worksheet.merge_range('A7:P7', 'SUMMARY REPORT', center_bold_style)
            worksheet.write('A8', 'Outlet', header_style)
            worksheet.write('B8', 'Region', header_style)
            worksheet.write('C8', 'Area', header_style)
            worksheet.write('D8', 'Regional Manager', header_style)
            worksheet.write('E8', 'Area Manager', header_style)
            worksheet.write('F8', 'Date', header_style)
            worksheet.write('G8', 'Total Cancelled Receipts(qty)', header_style)
            worksheet.write('H8', 'Total Cancelled Receipts(RM)', header_style)
            worksheet.write('I8', 'Total Deleted Menu(qty)', header_style)
            worksheet.write('J8', 'Total Deleted Menu(RM)', header_style)
            worksheet.write('K8', 'Total Back Button(qty)', header_style)
            worksheet.write('L8', 'Total Back Button(RM)', header_style)
            worksheet.write('M8', 'Total Destroy Order(qty)', header_style)
            worksheet.write('N8', 'Total Destroy Order(RM)', header_style)
            worksheet.write('O8', 'Total Manual Credit Card(qty)', header_style)
            worksheet.write('P8', 'Total Manual Credit Card(RM)', header_style)

            row = 9
            summary_data = self._get_summary_data(credentials)
            for summary in summary_data:
                worksheet.write('A%s' % row, summary['outlet_name'],
                                line_style)
                worksheet.write('B%s' % row, summary['region_name'],
                                line_style)
                worksheet.write('C%s' % row, summary['area_name'],
                                line_style)
                worksheet.write('D%s' % row, summary['region_mng'],
                                line_style)
                worksheet.write('E%s' % row, summary['area_mng'],
                                line_style)
                worksheet.write('F%s' % row, summary['order_date'],
                                date_style
                                if self.break_down_by == 'day'
                                else month_style)
                worksheet.write('G%s' % row, summary['cancel_receipt'],
                                line_style)
                worksheet.write('H%s' % row, summary['total_cancel_receipt'],
                                line_style)
                worksheet.write('I%s' % row, summary['delete_menu_name'],
                                line_style)
                worksheet.write('J%s' % row, summary['total_delete_menu_name'],
                                line_style)
                worksheet.write('K%s' % row, summary['back_button'],
                                line_style)
                worksheet.write('L%s' % row, summary['total_back_button'],
                                line_style)
                worksheet.write('M%s' % row, summary['destroy_transaction'],
                                line_style)
                worksheet.write('N%s' % row,
                                summary['total_destroy_transaction'],
                                line_style)
                worksheet.write('O%s' % row, summary['manual_credit_card'],
                                line_style)
                worksheet.write('P%s' % row,
                                summary['total_manual_credit_card'],
                                line_style)
                row += 1
        elif self.report_type == 'detailed':
            # Detailed Report
            worksheet.set_row(6, 45)
            worksheet.merge_range('A6:P6', 'DETAILS REPORT', center_bold_style)
            worksheet.write('A7', 'Outlet', header_style)
            worksheet.write('B7', 'Region', header_style)
            worksheet.write('C7', 'Area', header_style)
            worksheet.write('D7', 'Regional Manager', header_style)
            worksheet.write('E7', 'Area Manager', header_style)
            worksheet.write('F7', 'PIC', header_style)
            worksheet.write('G7', 'Cashier',
                            header_style)
            worksheet.write('H7', 'Date / Time', header_style)
            worksheet.write('I7', 'Invoice No', header_style)
            worksheet.write('J7', 'Menu Name', header_style)
            worksheet.write('K7', 'Method of Cancellation', header_style)
            worksheet.write('L7', 'Qty', header_style)
            worksheet.write('M7', 'Value', header_style)
            worksheet.write('N7', 'Remarks', header_style)

            row = 8
            details_data = self._get_details_data(credentials)
            for detail in details_data:
                worksheet.write('A%s' % row, detail['outlet_name'], line_style)
                worksheet.write('B%s' % row, detail['region_name'], line_style)
                worksheet.write('C%s' % row, detail['area_name'], line_style)
                worksheet.write('D%s' % row, detail['region_mng'], line_style)
                worksheet.write('E%s' % row, detail['area_mng'], line_style)
                worksheet.write('F%s' % row, detail['pic_name'], line_style)
                worksheet.write('G%s' % row, detail['cashier_name'], line_style)
                worksheet.write('H%s' % row, detail['date'],  date_style)
                worksheet.write('I%s' % row, detail['invoice_no'], line_style)
                worksheet.write('J%s' % row, detail['menu_name'], line_style)
                worksheet.write('K%s' % row, CANCEL_METHODS[detail['method']],
                                line_style)
                worksheet.write('L%s' % row, detail['qty'], line_style)
                worksheet.write('M%s' % row, detail['unit_price'], line_style)
                worksheet.write('N%s' % row, detail['remark'], line_style)
                row += 1
        # end of report data
        workbook.close()
        out = base64.encodestring(fp.getvalue())
        self.write({'file_name': out, 'name': filename})
        fp.close()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=pos.track.order.report&field=file_name&id=%s&filename=%s.xls' % (
                self.id, filename),
            'target': 'self',
        }
