# --*-- coding: utf-8 --*--

from openerp import fields, models, api, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_round
import pytz
from datetime import datetime, timedelta

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class pos_menu_data(models.TransientModel):
    _name = 'pos.menu.data'

    start_date = fields.Date(string=_("Start date"))
    end_date = fields.Date(string=_("End date"))
    outlet_ids = fields.Many2many(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_point_of_sale.pos_menu_report')


class pos_menu_report(ReportXlsx):
    _name = 'report.br_point_of_sale.pos_menu_report'

    def convert_timezone(self, date):
        # from_tz = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT).replace(tzinfo=pytz.timezone(from_tz))
        # to_tz = from_tz.astimezone(pytz.timezone(to_tz))
        # return to_tz.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        # TODO: +8 timezone should be loaded from common configuration
        new_date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(hours=8)
        return new_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def _get_tax_amount(self, line_master, amount):
        cur = line_master.order_id.pricelist_id.currency_id
        taxes_ids = [tax for tax in line_master.tax_ids if tax.company_id.id == line_master.order_id.company_id.id]
        fiscal_position_id = line_master.order_id.fiscal_position_id
        if fiscal_position_id:
            taxes_ids = fiscal_position_id.map_tax(taxes_ids)
        # price = line_master.price_unit
        tax_amount = 0
        if taxes_ids:
            taxes = taxes_ids[0].compute_all(amount, cur, 1, product=line_master.product_id,
                                             partner=line_master.order_id.partner_id or False)
            tax_amount = taxes['total_included'] - taxes['total_excluded']
        return tax_amount

    def get_timezone_offset(self):
        tz = pytz.timezone(self.env.user.tz).localize(datetime.now()).strftime('%z')
        # Timezone offset's format is for example: +0700, -1000,...
        return tz[:-2]

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

        table_row_date = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy',
        })
        cell_date = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy',
        })
        table_row_time = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'hh:mm:ss',
        })

        table_row_datetime = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy hh:mm:ss',
        })

        outlet_names = []
        outlet_ids = []
        for x in report.outlet_ids:
            outlet_names.append(x.name)
            outlet_ids.append(x.id)

        # SET COLUMNS'S WIDTH
        vertical_border = wb.add_format({
            'border': 1,
        })
        no_border = wb.add_format({
            'border': 0,
        })
        ws.set_column(0, 46, 30)
        # ws.set_row(0, None, no_border)
        # ws.set_row(1, None, no_border)
        # ws.set_row(2, None, no_border)
        # ws.set_row(3, None, no_border)
        # ws.set_row(4, None, no_border)

        # REPORT'S HEADER
        ws.write('A1', u'Start Date', bold)
        ws.write('A2', u'End Date', bold)
        ws.write('A3', u'Outlet(s)', bold)
        ws.write_datetime('B1', datetime.strptime(report.start_date, "%Y-%m-%d"), cell_date)
        ws.write_datetime('B2', datetime.strptime(report.end_date, "%Y-%m-%d"), cell_date)
        ws.write('B3', ', '.join(outlet_names))

        # ------------------- Header -------------------
        ws.write('A5', 'Outlet', table_header)
        ws.write('B5', 'Outlet Code', table_header)
        ws.write('C5', 'Analytic Account', table_header)
        ws.write('D5', 'Area', table_header)
        ws.write('E5', 'Parent Area', table_header)
        ws.write('F5', 'Region', table_header)
        ws.write('G5', 'Asset Type', table_header)
        ws.write('H5', 'Location Type', table_header)
        ws.write('I5', 'Outlet Type', table_header)
        ws.write('J5', 'Outlet Status', table_header)
        ws.write('K5', 'Regional Manager', table_header)
        ws.write('L5', 'Area Manager', table_header)
        ws.write('M5', 'Outlet PIC 1', table_header)
        ws.write('N5', 'Outlet PIC 2', table_header)
        ws.write('O5', 'Outlet PIC 3', table_header)
        ws.write('P5', 'Sales Person', table_header)
        ws.write('Q5', 'Session', table_header)
        ws.write('R5', 'Session Start Date', table_header)
        ws.write('S5', 'Session Close Date', table_header)
        ws.write('T5', 'PIC', table_header)
        ws.write('U5', 'Order Date', table_header)
        ws.write('V5', 'Order Time', table_header)
        ws.write('W5', 'Order Ref', table_header)
        ws.write('X5', 'Invoice Number (Not In Use)', table_header)
        ws.write('Y5', 'Invoice Number', table_header)
        ws.write('Z5', 'Customer Name', table_header)
        ws.write('AA5', 'Menu Number', table_header)
        ws.write('AB5', 'Menu Name', table_header)
        ws.write('AC5', 'Menu Category 1', table_header)
        ws.write('AD5', 'Menu Category 2', table_header)
        ws.write('AE5', 'Menu Category 3', table_header)
        ws.write('AF5', 'Menu Category 4', table_header)
        ws.write('AG5', 'Is Not A Sales Transaction', table_header)
        ws.write('AH5', 'Discount Name', table_header)
        ws.write('AI5', 'Discount Category 1', table_header)
        ws.write('AJ5', 'Discount Category 2', table_header)
        ws.write('AK5', 'Discount Category 3', table_header)
        ws.write('AL5', 'Discount Category 4', table_header)
        ws.write('AM5', 'Total Before Discount', table_header)
        ws.write('AN5', 'Discount', table_header)
        ws.write('AO5', 'Total After Discount', table_header)
        ws.write('AP5', 'Tax Before Discount', table_header)
        ws.write('AQ5', 'Tax On Discount', table_header)
        ws.write('AR5', 'Tax After Discount', table_header)
        ws.write('AS5', 'Total Sales', table_header)
        ws.write('AT5', 'Net Total', table_header)
        ws.write('AU5', 'Sale Date', table_header)
        ws.write('AV5', 'Not A Transaction', table_header)

        # FILL DATA
        def cutoff_time(date):
            """
            :param date: UTC datetime
            :return: Converted date from GMT+8 to UTC then cutoff 5 hours
            """
            date = datetime.strptime(date, DATE_FORMAT) - timedelta(hours=3)
            return date.strftime(DATE_FORMAT)

        start_date = report.start_date + ' 00:00:00'
        utc_start_date = cutoff_time(start_date)

        end_date = report.end_date + ' 23:59:59'
        utc_end_date = cutoff_time(end_date)

        sql_oulet_string = '1=1'
        if outlet_ids:
            sql_oulet_string = 'po.outlet_id in ' + str(outlet_ids).replace('[', '(').replace(']', ')')

        credentials = {
            'user_id_report': self.env.user.id,
            'sql_oulet_string': sql_oulet_string,
            'start_date': utc_start_date,
            'end_date': utc_end_date,
            'rounding_product_id': self.env.user.company_id.rounding_product_id.id
        }

        report_data = self.get_report_data(credentials)
        adjustment_lines = self._get_adjustment_lines(credentials)
        order_ref = report_data[0]['order_ref'] if len(report_data) > 0 else ''
        total_discount_product_line = 0
        total_discount_product_line_tax = 0

        row = 6
        for line in report_data:
            if order_ref != line['order_ref']:
                if order_ref in adjustment_lines:
                    # Write adjustment line per each order
                    for adjustment in adjustment_lines[order_ref]:

                        ws.write('A%s' % row, prev_line['outlet'], table_row_left)
                        ws.write('B%s' % row, prev_line['outlet_code'], table_row_left)
                        ws.write('C%s' % row, prev_line['analytic_account'], table_row_left)
                        ws.write('D%s' % row, prev_line['area'], table_row_left)
                        ws.write('E%s' % row, prev_line['parent_area'], table_row_left)
                        ws.write('F%s' % row, prev_line['region'], table_row_left)
                        ws.write('G%s' % row, prev_line['asset_type'], table_row_left)
                        ws.write('H%s' % row, prev_line['location_type'], table_row_left)
                        ws.write('I%s' % row, prev_line['outlet_type'], table_row_left)
                        ws.write('J%s' % row, prev_line['outlet_status'], table_row_left)
                        ws.write('K%s' % row, prev_line['regional_manager'], table_row_left)
                        ws.write('L%s' % row, prev_line['area_manager'], table_row_left)
                        ws.write('M%s' % row, prev_line['pic1'], table_row_left)
                        ws.write('N%s' % row, prev_line['pic2'], table_row_left)
                        ws.write('O%s' % row, prev_line['pic3'], table_row_left)
                        ws.write('P%s' % row, prev_line['sale_person'], table_row_left)
                        ws.write('Q%s' % row, prev_line['session_name'], table_row_left)
                        ws.write_datetime('R%s' % row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                        if prev_line['stop_at']:
                            stop_at = self.convert_timezone(prev_line['stop_at'])
                            ws.write_datetime('S%s' % row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                        else:
                            stop_at = ""
                            ws.write('S%s' % row, stop_at, table_row_left)
                        ws.write('T%s' % row, prev_line['sale_person'], table_row_left)
                        date_order = self.convert_timezone('%s %s' % (prev_line['order_date'], prev_line['order_time']))
                        ws.write_datetime('U%s' % row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
                        ws.write_datetime('V%s' % row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"), table_row_time)
                        ws.write('W%s' % row, prev_line['order_ref'], table_row_left)
                        ws.write('X%s' % row, prev_line['invoice_no'], table_row_left)
                        ws.write('Y%s' % row, prev_line['pos_reference'], table_row_left)
                        ws.write('Z%s' % row, prev_line['customer_name'], table_row_left)

                        ws.write('AA%s' % row, '', table_row_right)
                        ws.write('AB%s' % row, adjustment['adjustment_name'], table_row_left)
                        ws.write('AC%s' % row, '', table_row_left)
                        ws.write('AD%s' % row, '', table_row_left)
                        ws.write('AE%s' % row, '', table_row_left)
                        ws.write('AF%s' % row, '', table_row_left)
                        ws.write('AG%s' % row, prev_line['non_sale'], table_row_right)
                        ws.write('AH%s' % row, '', table_row_left)
                        ws.write('AI%s' % row, '', table_row_left)
                        ws.write('AJ%s' % row, '', table_row_left)
                        ws.write('AK%s' % row, '', table_row_left)
                        ws.write('AL%s' % row, '', table_row_left)

                        if adjustment['adjustment_name'] == "Tax Adjustment":
                            ws.write('AM%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                            ws.write('AN%s' % row, 0, table_row_right)
                            ws.write('AO%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                            ws.write('AP%s' % row, 0, table_row_right)
                            ws.write('AQ%s' % row, 0, table_row_right)
                            ws.write('AR%s' % row, adjustment['gst_after_discount'], table_row_right)
                            ws.write('AS%s' % row, 0, table_row_right)
                            ws.write('AT%s' % row, adjustment['gst_after_discount']* -1, table_row_right)
                        elif adjustment['adjustment_name'] == "Price Rounding":
                            ws.write('AM%s' % row, adjustment['price_with_tax'], table_row_right)
                            ws.write('AN%s' % row, 0, table_row_right)
                            ws.write('AO%s' % row, adjustment['price_with_tax'], table_row_right)
                            ws.write('AP%s' % row, adjustment['tax'], table_row_right)
                            ws.write('AQ%s' % row, 0, table_row_right)
                            ws.write('AR%s' % row, adjustment['tax'], table_row_right)
                            ws.write('AS%s' % row, adjustment['price_with_tax'] + adjustment['tax'], table_row_right)
                            ws.write('AT%s' % row, adjustment['price_with_tax'], table_row_right)
                        elif adjustment['adjustment_name'] == "Bill Rounding":
                            ws.write('AM%s' % row, 0, table_row_right)
                            ws.write('AN%s' % row, 0, table_row_right)
                            ws.write('AO%s' % row, 0, table_row_right)
                            ws.write('AP%s' % row, 0, table_row_right)
                            ws.write('AQ%s' % row, 0, table_row_right)
                            ws.write('AR%s' % row, 0, table_row_right)
                            ws.write('AS%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                            ws.write('AT%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                        elif adjustment['adjustment_name'] == "Discount/TaxVar":
                            total_dicount_variance = (adjustment['total_discount_line'] or 0) - total_discount_product_line
                            discount_tax_variance = (adjustment['total_discount_line_tax'] or 0) - total_discount_product_line_tax
                            ws.write('AM%s' % row, 0, table_row_right)
                            ws.write('AN%s' % row, total_dicount_variance , table_row_right)
                            ws.write('AO%s' % row, total_dicount_variance , table_row_right)
                            ws.write('AP%s' % row, 0, table_row_right)
                            ws.write('AQ%s' % row, discount_tax_variance, table_row_right)
                            ws.write('AR%s' % row, discount_tax_variance, table_row_right)
                            ws.write('AS%s' % row, total_dicount_variance + discount_tax_variance, table_row_right)
                            ws.write('AT%s' % row, total_dicount_variance, table_row_right)

                        ws.write_datetime('AU%s' % row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
                        ws.write('AV%s' % row, any([prev_line['non_sale'], prev_line['is_refund'], prev_line['is_refunded']]) and 'YES' or 'NO', table_row_left)
                        row += 1
                order_ref = line['order_ref']
                total_discount_product_line = 0
                total_discount_product_line_tax = 0
            prev_line = line
            ws.write('A%s' % row, line['outlet'], table_row_left)
            ws.write('B%s' % row, line['outlet_code'], table_row_left)
            ws.write('C%s' % row, line['analytic_account'], table_row_left)
            ws.write('D%s' % row, line['area'], table_row_left)
            ws.write('E%s' % row, line['parent_area'], table_row_left)
            ws.write('F%s' % row, line['region'], table_row_left)
            ws.write('G%s' % row, line['asset_type'], table_row_left)
            ws.write('H%s' % row, line['location_type'], table_row_left)
            ws.write('I%s' % row, line['outlet_type'], table_row_left)
            ws.write('J%s' % row, line['outlet_status'], table_row_left)
            ws.write('K%s' % row, line['regional_manager'], table_row_left)
            ws.write('L%s' % row, line['area_manager'], table_row_left)
            ws.write('M%s' % row, line['pic1'], table_row_left)
            ws.write('N%s' % row, line['pic2'], table_row_left)
            ws.write('O%s' % row, line['pic3'], table_row_left)
            ws.write('P%s' % row, line['sale_person'], table_row_left)
            ws.write('Q%s' % row, line['session_name'], table_row_left)
            start_at = self.convert_timezone(line['start_at'])
            ws.write_datetime('R%s' % row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
            if line['stop_at']:
                stop_at = self.convert_timezone(line['stop_at'])
                ws.write_datetime('S%s' % row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
            else:
                stop_at = ""
                ws.write('S%s' % row, stop_at, table_row_left)
            ws.write('T%s' % row, line['sale_person'], table_row_left)
            date_order = self.convert_timezone('%s %s' % (line['order_date'], line['order_time']))
            ws.write_datetime('U%s' % row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
            ws.write_datetime('V%s' % row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"), table_row_time)
            ws.write('W%s' % row, line['order_ref'], table_row_left)
            ws.write('X%s' % row, line['invoice_no'], table_row_left)
            ws.write('Y%s' % row, line['pos_reference'], table_row_left)
            ws.write('Z%s' % row, line['customer_name'], table_row_left)
            ws.write('AA%s' % row, line['menu_number'], table_row_right)
            ws.write('AB%s' % row, line['menu_name'], table_row_left)
            menu_categ_name = line['menu_category'].split("/") if line['menu_category'] else ""
            categ_len = len(menu_categ_name)
            ws.write('AC%s' % row, menu_categ_name[0].strip() if categ_len > 0 else "", table_row_left)
            ws.write('AD%s' % row, menu_categ_name[1].strip() if categ_len > 1 else "", table_row_left)
            ws.write('AE%s' % row, menu_categ_name[2].strip() if categ_len > 2 else "", table_row_left)
            ws.write('AF%s' % row, menu_categ_name[3].strip() if categ_len > 3 else "", table_row_left)
            ws.write('AG%s' % row, line['non_sale'], table_row_right)

            promotion_row = row
            if line['promotions']:
                promotions = line['promotions'].split("|")
                for p in promotions:
                    p_data = p.split('###')
                    p_name = p_data[0]
                    p_categ = p_data[1].split("/")
                    promotion_categ_len = len(p_categ)
                    if p_name:
                        if promotion_row > row:
                            ws.write('A%s' % promotion_row, '', table_row_left)
                            ws.write('B%s' % promotion_row, '', table_row_left)
                            ws.write('C%s' % promotion_row, '', table_row_left)
                            ws.write('D%s' % promotion_row, '', table_row_left)
                            ws.write('E%s' % promotion_row, '', table_row_left)
                            ws.write('F%s' % promotion_row, '', table_row_left)
                            ws.write('G%s' % promotion_row, '', table_row_left)
                            ws.write('H%s' % promotion_row, '', table_row_left)
                            ws.write('I%s' % promotion_row, '', table_row_left)
                            ws.write('J%s' % promotion_row, '', table_row_left)
                            ws.write('K%s' % promotion_row, '', table_row_left)
                            ws.write('L%s' % promotion_row, '', table_row_left)
                            ws.write('M%s' % promotion_row, '', table_row_left)
                            ws.write('N%s' % promotion_row, '', table_row_left)
                            ws.write('O%s' % promotion_row, '', table_row_left)
                            ws.write('P%s' % promotion_row, '', table_row_left)
                            ws.write('Q%s' % promotion_row, '', table_row_left)
                            ws.write('R%s' % promotion_row, '', table_row_left)
                            ws.write('S%s' % promotion_row, '', table_row_left)
                            ws.write('T%s' % promotion_row, '', table_row_left)
                            ws.write('U%s' % promotion_row, '', table_row_left)
                            ws.write('V%s' % promotion_row, '', table_row_left)
                            ws.write('W%s' % promotion_row, '', table_row_left)
                            ws.write('X%s' % promotion_row, '', table_row_left)
                            ws.write('Y%s' % promotion_row, '', table_row_left)
                            ws.write('Z%s' % promotion_row, '', table_row_left)

                            ws.write('AA%s' % promotion_row, '', table_row_left)
                            ws.write('AB%s' % promotion_row, '', table_row_left)
                            ws.write('AC%s' % promotion_row, '', table_row_left)
                            ws.write('AD%s' % promotion_row, '', table_row_left)
                            ws.write('AE%s' % promotion_row, '', table_row_left)
                            ws.write('AF%s' % promotion_row, '', table_row_left)
                            ws.write('AG%s' % promotion_row, '', table_row_left)

                            ws.write('AM%s' % promotion_row, '', table_row_left)
                            ws.write('AN%s' % promotion_row, '', table_row_left)
                            ws.write('AO%s' % promotion_row, '', table_row_left)
                            ws.write('AP%s' % promotion_row, '', table_row_left)
                            ws.write('AQ%s' % promotion_row, '', table_row_left)
                            ws.write('AR%s' % promotion_row, '', table_row_left)
                            ws.write('AS%s' % promotion_row, '', table_row_left)


                        # Bind promotion data
                        ws.write('AH%s' % promotion_row, p_name, table_row_left)
                        ws.write('AI%s' % promotion_row, p_categ[0] if promotion_categ_len > 0 else "",
                                 table_row_left)
                        ws.write('AJ%s' % promotion_row, p_categ[1] if promotion_categ_len > 1 else "",
                                 table_row_left)
                        ws.write('AK%s' % promotion_row, p_categ[2] if promotion_categ_len > 2 else "",
                                 table_row_right)
                        ws.write('AL%s' % promotion_row, p_categ[3] if promotion_categ_len > 3 else "",
                                 table_row_left)
                        promotion_row += 1
                    else:
                        ws.write('AH%s' % promotion_row, '', table_row_left)
                        ws.write('AI%s' % promotion_row, '', table_row_left)
                        ws.write('AJ%s' % promotion_row, '', table_row_left)
                        ws.write('AK%s' % promotion_row, '', table_row_left)
                        ws.write('AL%s' % promotion_row, '', table_row_left)

            # Total Before Discount (A1)
            ws.write('AM%s' % row, line['amount_w_tax'] or 0, table_row_right)
            # Discount(A2)
            ws.write('AN%s' % row, -1 * (line['discount_amount'] or 0), table_row_right)
            total_discount_product_line += -1 * (line['discount_amount'] or 0)
            # Total After Discount (A3)
            total_after_discount = (line['amount_w_tax'] or 0) - (line['discount_amount'] or 0)
            ws.write('AO%s' % row, total_after_discount, table_row_right)
            # GST on A1 (B1)
            ws.write('AP%s' % row, line['tax'] or 0, table_row_right)
            # GST on A2 (B2)
            ws.write('AQ%s' % row, -1 * (line['tax_discount'] or 0), table_row_right)
            total_discount_product_line_tax += -1 * (line['tax_discount'] or 0)
            # GST on A3 (B3)
            ws.write('AR%s' % row, (line['tax'] or 0) - (line['tax_discount'] or 0), table_row_right)
            ws.write('AS%s' % row, total_after_discount + (line['tax'] or 0) - (line['tax_discount'] or 0), table_row_right)
            # Nett Total (A3-B3)
            ws.write('AT%s' % row, total_after_discount , table_row_right)
            # Sale Date
            sale_date = self.convert_timezone('%s %s' % (line['order_date'], line['order_time']))
            sale_date = datetime.strptime(sale_date, '%Y-%m-%d %H:%M:%S')
            if sale_date.hour < 5:
                sale_date = sale_date - timedelta(hours=5)

            ws.write_datetime('AU%s' % row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
            ws.write('AV%s' % row, any([line['non_sale'], line['is_refund'], line['is_refunded']]) and 'YES' or 'NO', table_row_left)
            row += (promotion_row - row) + 1 if promotion_row == row else (promotion_row - row)
        else:
            if order_ref in adjustment_lines:
                # Write adjustment line per each order
                for adjustment in adjustment_lines[order_ref]:
                    ws.write('A%s' % row, prev_line['outlet'], table_row_left)
                    ws.write('B%s' % row, prev_line['outlet_code'], table_row_left)
                    ws.write('C%s' % row, prev_line['analytic_account'], table_row_left)
                    ws.write('D%s' % row, prev_line['area'], table_row_left)
                    ws.write('E%s' % row, prev_line['parent_area'], table_row_left)
                    ws.write('F%s' % row, prev_line['region'], table_row_left)
                    ws.write('G%s' % row, prev_line['asset_type'], table_row_left)
                    ws.write('H%s' % row, prev_line['location_type'], table_row_left)
                    ws.write('I%s' % row, prev_line['outlet_type'], table_row_left)
                    ws.write('J%s' % row, prev_line['outlet_status'], table_row_left)
                    ws.write('K%s' % row, prev_line['regional_manager'], table_row_left)
                    ws.write('L%s' % row, prev_line['area_manager'], table_row_left)
                    ws.write('M%s' % row, prev_line['pic1'], table_row_left)
                    ws.write('N%s' % row, prev_line['pic2'], table_row_left)
                    ws.write('O%s' % row, prev_line['pic3'], table_row_left)
                    ws.write('P%s' % row, prev_line['sale_person'], table_row_left)
                    ws.write('Q%s' % row, prev_line['session_name'], table_row_left)
                    ws.write_datetime('R%s' % row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                    if prev_line['stop_at']:
                        stop_at = self.convert_timezone(prev_line['stop_at'])
                        ws.write_datetime('S%s' % row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                    else:
                        stop_at = ""
                        ws.write('S%s' % row, stop_at, table_row_left)
                    ws.write('T%s' % row, prev_line['sale_person'], table_row_left)
                    date_order = self.convert_timezone('%s %s' % (prev_line['order_date'], prev_line['order_time']))
                    ws.write_datetime('U%s' % row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
                    ws.write_datetime('V%s' % row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"), table_row_time)
                    ws.write('W%s' % row, prev_line['order_ref'], table_row_left)
                    ws.write('X%s' % row, prev_line['invoice_no'], table_row_left)
                    ws.write('Y%s' % row, prev_line['pos_reference'], table_row_left)
                    ws.write('Z%s' % row, prev_line['customer_name'], table_row_left)

                    ws.write('AA%s' % row, '', table_row_right)
                    ws.write('AB%s' % row, adjustment['adjustment_name'], table_row_left)
                    ws.write('AC%s' % row, '', table_row_left)
                    ws.write('AD%s' % row, '', table_row_left)
                    ws.write('AE%s' % row, '', table_row_left)
                    ws.write('AF%s' % row, '', table_row_left)
                    ws.write('AG%s' % row, prev_line['non_sale'], table_row_right)
                    ws.write('AH%s' % row, '', table_row_left)
                    ws.write('AI%s' % row, '', table_row_left)
                    ws.write('AJ%s' % row, '', table_row_left)
                    ws.write('AK%s' % row, '', table_row_left)
                    ws.write('AL%s' % row, '', table_row_left)
                    # print "type ---",adjustment['adjustment_name']
                    if adjustment['adjustment_name'] == "Tax Adjustment":
                        ws.write('AM%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                        ws.write('AN%s' % row, 0, table_row_right)
                        ws.write('AO%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                        ws.write('AP%s' % row, 0, table_row_right)
                        ws.write('AQ%s' % row, 0, table_row_right)
                        ws.write('AR%s' % row, adjustment['gst_after_discount'], table_row_right)
                        ws.write('AS%s' % row, 0, table_row_right)
                        ws.write('AT%s' % row, adjustment['gst_after_discount'] * -1 , table_row_right)
                    elif adjustment['adjustment_name'] == "Price Rounding":
                        ws.write('AM%s' % row, adjustment['price_with_tax'], table_row_right)
                        ws.write('AN%s' % row, 0, table_row_right)
                        ws.write('AO%s' % row, adjustment['price_with_tax'], table_row_right)
                        ws.write('AP%s' % row, adjustment['tax'], table_row_right)
                        ws.write('AQ%s' % row, 0, table_row_right)
                        ws.write('AR%s' % row, adjustment['tax'], table_row_right)
                        ws.write('AS%s' % row, adjustment['price_with_tax'] + adjustment['tax'], table_row_right)
                        ws.write('AT%s' % row, adjustment['price_with_tax'], table_row_right)
                    elif adjustment['adjustment_name'] == "Bill Rounding":
                        ws.write('AM%s' % row, 0, table_row_right)
                        ws.write('AN%s' % row, 0, table_row_right)
                        ws.write('AO%s' % row, 0, table_row_right)
                        ws.write('AP%s' % row, 0, table_row_right)
                        ws.write('AQ%s' % row, 0, table_row_right)
                        ws.write('AR%s' % row, 0, table_row_right)
                        ws.write('AS%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                        ws.write('AT%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                    elif adjustment['adjustment_name'] == "Discount/TaxVar":
                        total_dicount_variance = (adjustment['total_discount_line'] or 0) - total_discount_product_line
                        discount_tax_variance = (adjustment['total_discount_line_tax'] or 0) - total_discount_product_line_tax
                        ws.write('AM%s' % row, 0, table_row_right)
                        ws.write('AN%s' % row, total_dicount_variance, table_row_right)
                        ws.write('AO%s' % row, total_dicount_variance, table_row_right)
                        ws.write('AP%s' % row, 0, table_row_right)
                        ws.write('AQ%s' % row, discount_tax_variance, table_row_right)
                        ws.write('AR%s' % row, discount_tax_variance, table_row_right)
                        ws.write('AS%s' % row, total_dicount_variance + discount_tax_variance, table_row_right)
                        ws.write('AT%s' % row, total_dicount_variance, table_row_right)

                    ws.write_datetime('AU%s' % row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
                    ws.write('AV%s' % row, any([line['non_sale'], line['is_refund'], line['is_refunded']]) and 'YES' or 'NO', table_row_left)
                    row += 1
    def get_report_data(self, args):
        sql = '''
        WITH promotion_products AS (
            SELECT
              po.id AS order_id,
              pc.discount_product_id,
              pc.discount_promotion_bundle_id,
              pc.discount_promotion_product_id
            FROM pos_order po
              INNER JOIN pos_session ps ON po.session_id = ps.id
              INNER JOIN pos_config pc ON ps.config_id = pc.id
            WHERE
              po.outlet_id IN
                  (SELECT br_multi_outlet_outlet_id
                   FROM br_multi_outlet_outlet_res_users_rel brrel
                   WHERE brrel.res_users_id = {user_id_report}
                   )
              AND {sql_oulet_string}
              AND po.date_order >= '{start_date}'
              AND po.date_order <= '{end_date}'
            GROUP BY po.id, pc.id
        ),
          promotion_tmp AS (
              SELECT
                pol.master_id,
                string_agg(DISTINCT concat(promotion.name, '###', promotion_categ.complete_name), '|') AS promotions
              FROM pos_order po
                LEFT JOIN pos_order_line pol ON po.id = pol.order_id
                LEFT JOIN pos_order_line_promotion_default_rel rel ON pol.id = rel.pos_order_line_id
                LEFT JOIN br_bundle_promotion promotion ON rel.promotion_id = promotion.id
                LEFT JOIN br_promotion_category promotion_categ ON promotion.promotion_category_id = promotion_categ.id
              WHERE
                po.outlet_id IN
                    (SELECT br_multi_outlet_outlet_id
                     FROM br_multi_outlet_outlet_res_users_rel brrel
                     WHERE brrel.res_users_id = {user_id_report}
                     )
                AND {sql_oulet_string}
                AND po.date_order >= '{start_date}'
                AND po.date_order <= '{end_date}'
              GROUP BY pol.master_id
          ),
        order_line_tmp AS (
          SELECT
            pol.master_id,
            pol_master.name AS menu_number,
            menu_categ.complete_name AS menu_category,
            product_master.name_template AS menu_name,
            pol.non_sale,
            coalesce(tax.price_include,false) as price_include,
            round(SUM(CASE WHEN coalesce(tax.price_include,false) = TRUE 
				THEN
					pol.discount_amount -  pol.discount_amount / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100)
				ELSE
					pol.discount_amount
				END) ,2)
			AS discount_amount	,
            SUM(ROUND(ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2)) AS tax,
            ROUND(SUM(pol.discount_amount / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100)) ,2)     AS tax_discount,
			SUM(CASE WHEN coalesce(tax.price_include,false) = TRUE 
				THEN
					ROUND( ROUND(pol.qty * pol.price_unit, 2) -  ROUND( ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100),2), 2)  																
				ELSE
					ROUND(pol.qty * pol.price_unit, 2)
				END)
			AS amount_w_tax
          FROM pos_order po
            LEFT JOIN pos_order_line pol ON po.id = pol.order_id
            LEFT JOIN _get_pos_order_line_tax(pol.id) tax ON tax.pol_id = pol.id
            LEFT JOIN promotion_products ON promotion_products.order_id = po.id
            LEFT JOIN br_pos_order_line_master pol_master ON pol.master_id = pol_master.id
            LEFT JOIN product_product product_master ON pol_master.product_id = product_master.id
            LEFT JOIN br_menu_category menu_categ ON product_master.menu_category_id = menu_categ.id
          WHERE
              po.outlet_id IN
                  (SELECT br_multi_outlet_outlet_id
                   FROM br_multi_outlet_outlet_res_users_rel brrel
                   WHERE brrel.res_users_id = {user_id_report}
                   )
              AND {sql_oulet_string}
              AND po.date_order >= '{start_date}'
              AND po.date_order <= '{end_date}'
          GROUP BY pol_master.id, pol.master_id, menu_categ.id, product_master.id, pol.non_sale, tax.price_include
        )
        SELECT
          bmoo.name                                                                   outlet,
          bmoo.code                                                                   outlet_code,
          aaa.name                                                                    analytic_account,
          rct.name                                                                    Area,
          rct_1.name                                                                  parent_area,
          region.name                                                                 region,
          outlet_type.name                                                            Asset_Type,
          outlet_type_1.name                                                          location_type,
          ho.outlet_type,
          ho.status                                                                   outlet_status,
          rp_1.name                                                                   Regional_Manager,
          rp_2.name                                                                   Area_Manager,
          resp_1.name                                                                 Pic1,
          resp_2.name                                                                 Pic2,
          resp_3.name                                                                 Pic3,
          ps.name                                                                     session_name,
          to_char(ps.start_at :: TIMESTAMP(0), 'YYYY-MM-DD HH24:MI:SS') start_at,
          to_char(ps.stop_at :: TIMESTAMP(0), 'YYYY-MM-DD HH24:MI:SS')  stop_at,
          rp_se.name                                                                  sale_person,
          date(po.date_order :: TIMESTAMP(0))                           order_date,
          to_char(po.date_order :: TIMESTAMP(0), 'HH24:MI:SS')          order_time,
          po.invoice_no,
          po.name                                                                     Order_Ref,
          po.pos_reference,
          r_partner.name                                                              Customer_Name,
          po.id                                                                       order_po_id,
          po.is_refund,
          po.is_refunded,
        --   Line Information
          promotion_tmp.promotions,
          order_line_tmp.price_include,
          order_line_tmp.menu_number,
          order_line_tmp.menu_name,
          order_line_tmp.menu_category,
          order_line_tmp.discount_amount,
          SUM(order_line_tmp.amount_w_tax) AS                  amount_w_tax,
          order_line_tmp.tax,
          order_line_tmp.tax_discount,
          order_line_tmp.non_sale
        FROM pos_order po
          LEFT JOIN get_history_outlet(po.outlet_id, po.date_order) ho ON po.outlet_id = ho.o_id
          INNER JOIN br_multi_outlet_outlet bmoo ON po.outlet_id = bmoo.id -- replace "bmoo" with "outlet"
          LEFT JOIN account_analytic_account aaa ON bmoo.analytic_account_id = aaa.id
          LEFT JOIN res_country_state rct ON ho.area = rct.id
          LEFT JOIN res_country_state rct_1 ON rct.parent_id = rct_1.id
          LEFT JOIN br_multi_outlet_region_area region ON region.id = ho.region
          LEFT JOIN br_multi_outlet_outlet_type outlet_type ON outlet_type.id = ho.asset_type
          LEFT JOIN br_multi_outlet_outlet_type outlet_type_1 ON ho.location_type = outlet_type_1.id
          LEFT JOIN res_users ru_1 ON ho.region_ma = ru_1.id
          LEFT JOIN res_partner rp_1 ON rp_1.id = ru_1.partner_id
          LEFT JOIN res_users ru_2 ON ho.area_ma = ru_2.id
          LEFT JOIN res_partner rp_2 ON rp_2.id = ru_2.partner_id
          LEFT JOIN res_users resu_1 ON ho.pic1 = resu_1.id
          LEFT JOIN res_partner resp_1 ON resp_1.id = resu_1.partner_id
          LEFT JOIN res_users resu_2 ON ho.pic2 = resu_2.id
          LEFT JOIN res_partner resp_2 ON resp_2.id = resu_2.partner_id
          LEFT JOIN res_users resu_3 ON ho.pic3 = resu_3.id
          LEFT JOIN res_partner resp_3 ON resp_3.id = resu_3.partner_id
          LEFT JOIN res_partner r_partner ON r_partner.id = po.partner_id
          LEFT JOIN pos_session ps ON ps.id = po.session_id
          LEFT JOIN res_users res_se ON ps.user_id = res_se.id
          LEFT JOIN res_partner rp_se ON res_se.partner_id = rp_se.id
          LEFT JOIN br_pos_order_line_master master_line ON po.id = master_line.order_id
          LEFT JOIN order_line_tmp ON order_line_tmp.master_id = master_line.id
          LEFT JOIN promotion_tmp ON promotion_tmp.master_id = master_line.id
        WHERE
          po.outlet_id IN
              (SELECT br_multi_outlet_outlet_id
               FROM br_multi_outlet_outlet_res_users_rel brrel
               WHERE brrel.res_users_id = {user_id_report}
               )
          AND {sql_oulet_string}
          AND po.date_order >= '{start_date}'
          AND po.date_order <= '{end_date}'
        GROUP BY bmoo.id, aaa.id, r_partner.id, rct.id, rct_1.id, region.id,
              outlet_type.id, outlet_type_1.id, rp_1.id, rp_2.id, resp_1.id,
              resp_2.id, resp_3.id, ps.id, rp_se.id, po.id,
              promotion_tmp.promotions,
              order_line_tmp.menu_number,
              order_line_tmp.menu_name,
              order_line_tmp.menu_category,
              order_line_tmp.discount_amount,
              order_line_tmp.price_include,
              order_line_tmp.tax,
              order_line_tmp.tax_discount,
              order_line_tmp.non_sale,
              ho.outlet_type,
              ho.status
        ORDER BY bmoo.name, ps.start_at, po.pos_reference;
              '''.format(**args)
        # print "sql order-->",sql
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def _get_adjustment_lines(self, args):
        """

        @return: dict - all adjustment for menuname report (rounding and gst)
        """

        def consolidate(adjustment_lines):
            res = {}
            for line in adjustment_lines:
                if line['pos_ref'] not in res:
                    res[line['pos_ref']] = [line]
                else:
                    res[line['pos_ref']].append(line)
            return res

        sql = """
            SELECT * FROM(
                    WITH promotion_products AS (
                        SELECT
                            po.id AS order_id,
                            pc.discount_product_id,
                            pc.discount_promotion_bundle_id,
                            pc.discount_promotion_product_id
                        FROM pos_order po
                        INNER JOIN pos_session ps ON po.session_id = ps.id
                        INNER JOIN pos_config pc ON ps.config_id = pc.id
                        WHERE po.outlet_id IN
                            (SELECT br_multi_outlet_outlet_id
                            FROM br_multi_outlet_outlet_res_users_rel brrel
                            WHERE brrel.res_users_id = {user_id_report})
                            AND {sql_oulet_string}
                            AND po.date_order >= '{start_date}'
                            AND po.date_order <= '{end_date}'
                        GROUP BY po.id, pc.id
                    ),
                    tax_line_amount_temp AS (
                        SELECT
                            pol.id AS pol_id,
                            tax.id AS taxid,
                            tax.amount AS amount,
                            coalesce(tax.price_include,false) AS price_include
                        FROM pos_order po
                        LEFT JOIN pos_order_line pol ON po.id = pol.order_id
                        LEFT JOIN _get_pos_order_line_tax(pol.id) tax ON tax.pol_id = pol.id
                        WHERE po.outlet_id IN
                            (SELECT br_multi_outlet_outlet_id
                            FROM br_multi_outlet_outlet_res_users_rel brrel
                            WHERE brrel.res_users_id = {user_id_report})
                            AND {sql_oulet_string}
                            AND po.date_order >= '{start_date}'
                            AND po.date_order <= '{end_date}'
                        GROUP BY pol.id, tax.id, tax.amount, tax.price_include
                    )
                    SELECT
                        po.name AS pos_ref,
                        'Discount/TaxVar' AS adjustment_name,
                
                        ROUND(COALESCE(sum(case when pol.product_id IN (promotion_products.discount_product_id, 
                                                                        promotion_products.discount_promotion_bundle_id, 
                                                                        promotion_products.discount_promotion_product_id)
                                                                        and tax.price_include
                                                then 
                                                    round( round( (pol.qty * pol.price_unit),2) - round(pol.qty * pol.price_unit,2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100) ,2)
                                                when pol.product_id IN (promotion_products.discount_product_id, 
                                                                        promotion_products.discount_promotion_bundle_id, 
                                                                        promotion_products.discount_promotion_product_id)
                                                                        and not tax.price_include
                                                then
                                                    pol.qty * pol.price_unit 
                                            end),0),2) as total_discount_line,
                                            
                           -- - case when tax.price_include
                           --         then 
                           --             sum( (pol.discount_amount - pol.discount_amount / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100)) * -1)
                           --         else
                           --             COALESCE(SUM(pol.discount_amount * -1), 0)
                           --   end
                        --, 2) 
                        --as total_dicount_variance,
                        
                        
                        
                        round(SUM(CASE WHEN pol.product_id  IN (promotion_products.discount_product_id, 
                                                                promotion_products.discount_promotion_bundle_id, 							 	
                                                                promotion_products.discount_promotion_product_id)
                                        THEN
                                            round(round(pol.qty * pol.price_unit ,2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100),2)
                
                                        ELSE 0 END
                        ),2) as total_discount_line_tax,
                        -- -
                        -- round( sum(pol.discount_amount / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100) ) * -1  ,2) 
                        -- AS discount_tax_variance,
                        0 AS gst_after_discount,
                        0 AS price_with_tax,
                        0 AS tax,
                        0 AS payment_amount,
                        tax.price_include as price_include,
                        4 as order_index
                    FROM pos_order po
                    left join pos_order_line pol on pol.order_id = po.id 
                    LEFT JOIN promotion_products ON promotion_products.order_id = po.id
                    LEFT JOIN tax_line_amount_temp tax ON tax.pol_id = pol.id
                    WHERE po.outlet_id IN
                        (SELECT br_multi_outlet_outlet_id
                        FROM br_multi_outlet_outlet_res_users_rel brrel
                        WHERE brrel.res_users_id = {user_id_report}
                        )
                        AND {sql_oulet_string}
                        AND po.date_order >= '{start_date}'
                        AND po.date_order <= '{end_date}'
                        
                    GROUP BY po.id ,tax.price_include
            UNION 
                SELECT
                    po.name AS pos_ref,
                    'Tax Adjustment'    AS adjustment_name,
                    0 as total_discount_line,
	                0 AS total_discount_line_tax,
                    COALESCE(SUM(tax_adjustment), 0) AS gst_after_discount,
                    0 AS price_with_tax,
                    0 AS tax,
                    0 AS payment_amount,
                    FALSE as price_include,
                    2 as order_index
                FROM pos_order po
                WHERE po.outlet_id IN
                    (SELECT br_multi_outlet_outlet_id
                    FROM br_multi_outlet_outlet_res_users_rel brrel
                    WHERE brrel.res_users_id = {user_id_report}
                    )
                    AND {sql_oulet_string}
                    AND po.date_order >= '{start_date}'
                    AND po.date_order <= '{end_date}'
                    AND po.tax_adjustment != 0
                GROUP BY po.id
            UNION
                SELECT
                    po.name AS pos_ref,
                    'Price Rounding',
                    0 as total_discount_line,
	                0 AS total_discount_line_tax,
                    ROUND(COALESCE(SUM(ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100)), 0), 2)           AS gst_after_discount,
                    ROUND(COALESCE(SUM(pol.price_unit * pol.qty), 0), 2) as price_with_tax,
                    SUM(ROUND(ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2)) AS tax,
                    0 AS payment_amount,
                    coalesce(tax.price_include,false) as price_include,
                    1 as order_index
                FROM pos_order po
                INNER JOIN pos_order_line pol ON po.id = pol.order_id AND pol.product_id = {rounding_product_id}
                LEFT JOIN _get_pos_order_line_tax(pol.id) tax ON tax.pol_id = pol.id
                WHERE po.outlet_id IN
                    (SELECT br_multi_outlet_outlet_id
                    FROM br_multi_outlet_outlet_res_users_rel brrel
                    WHERE brrel.res_users_id = {user_id_report}
                    )
                    AND {sql_oulet_string}
                    AND po.date_order >= '{start_date}'
                    AND po.date_order <= '{end_date}'
                GROUP BY po.id, tax.price_include
            
            UNION
                SELECT
                    po.name AS pos_ref,
                    'Bill Rounding',
                    0 as total_discount_line,
	                0 AS total_discount_line_tax,
                    0 AS gst_after_discount,
                    0 AS price_with_tax,
                    0 AS tax,
                    SUM(absl.amount) AS payment_amount,
                    FALSE as price_include,
                    3 as order_index
                FROM pos_order po
                LEFT JOIN account_bank_statement_line absl ON po.id = absl.pos_statement_id
                LEFT JOIN account_journal aj ON absl.journal_id = aj.id 
                WHERE po.outlet_id IN
                    (SELECT br_multi_outlet_outlet_id
                    FROM br_multi_outlet_outlet_res_users_rel brrel
                    WHERE brrel.res_users_id = {user_id_report}
                    )
                    AND {sql_oulet_string}
                    AND po.date_order >= '{start_date}'
                    AND po.date_order <= '{end_date}'
                    AND aj.is_rounding_method = True
                GROUP BY po.id
            
            ) adjustments ORDER BY pos_ref, order_index;
        """.format(**args)
        self.env.cr.execute(sql)
        # print "sql tax-->", sql
        return consolidate(self.env.cr.dictfetchall())

    def get_workbook_options(self):
        return {}


pos_menu_report('report.br_point_of_sale.pos_menu_report', 'pos.menu.data')
