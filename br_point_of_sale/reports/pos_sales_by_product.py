# --*-- coding: utf-8 --*--

from openerp import fields, models, api, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz


class pos_order_data(models.TransientModel):
    _name = 'pos.order.data'

    start_date = fields.Date(string=_("Start date"))
    end_date = fields.Date(string=_("End date"))
    outlet_ids = fields.Many2many(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_point_of_sale.pos_order_report')


class pos_order_report(ReportXlsx):
    _name = 'report.br_point_of_sale.pos_order_report'

    def convert_timezone(self, date):
        # from_tz = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT).replace(tzinfo=pytz.timezone(from_tz))
        # to_tz = from_tz.astimezone(pytz.timezone(to_tz))
        # return to_tz.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        # TODO: remove +8 timezone hardcode
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
        ws.set_column(0, 52, 30)
        # ws.set_row(0, None, no_border)
        # ws.set_row(1, None, no_border)
        # ws.set_row(2, None, no_border)
        # ws.set_row(3, None, no_border)
        # ws.set_row(4, None, no_border)

        # REPORT'S HEADER
        ws.write('A1', u'Start Date', bold)
        ws.write('A2', u'End Date', bold)
        ws.write('A3', u'Outlet(s)', bold)
        ws.write('B1', report.start_date)
        ws.write('B2', report.end_date)
        ws.write('B3', ', '.join(outlet_names))

        # ------------------- Header -------------------
        ws.write('A5', 'Outlet', table_header)
        ws.write('B5', 'Outlet Code', table_header)
        ws.write('C5', 'Analytic Account', table_header)
        ws.write('D5', 'Parent Area', table_header)
        ws.write('E5', 'Region', table_header)
        ws.write('F5', 'Asset Type', table_header)
        ws.write('G5', 'Location Type', table_header)
        ws.write('H5', 'Outlet Type', table_header)
        ws.write('I5', 'Outlet Status', table_header)
        ws.write('J5', 'Regional Manager', table_header)
        ws.write('K5', 'Area Manager', table_header)
        ws.write('L5', 'Outlet PIC 1', table_header)
        ws.write('M5', 'Outlet PIC 2', table_header)
        ws.write('N5', 'Outlet PIC 3', table_header)
        ws.write('O5', 'Sales Person', table_header)
        ws.write('P5', 'Session', table_header)
        ws.write('Q5', 'Session Start Date', table_header)
        ws.write('R5', 'Session Close Date', table_header)
        ws.write('S5', 'PIC', table_header)
        ws.write('T5', 'Order Date', table_header)
        ws.write('U5', 'Order Time', table_header)
        ws.write('V5', 'Order Ref', table_header)
        ws.write('W5', 'Invoice Number (Not In Use)', table_header)
        ws.write('X5', 'Invoice Number', table_header)
        ws.write('Y5', 'Customer Name', table_header)
        ws.write('Z5', 'Menu Number', table_header)
        ws.write('AA5', 'Menu Name', table_header)
        ws.write('AB5', 'Menu Category 1', table_header)
        ws.write('AC5', 'Menu Category 2', table_header)
        ws.write('AD5', 'Menu Category 3', table_header)
        ws.write('AE5', 'Menu Category 4', table_header)
        ws.write('AF5', 'Product', table_header)
        ws.write('AG5', 'Product Quantity', table_header)
        ws.write('AH5', 'UOM', table_header)
        ws.write('AI5', 'Product Category 1', table_header)
        ws.write('AJ5', 'Product Category 2', table_header)
        ws.write('AK5', 'Product Category 3', table_header)
        ws.write('AL5', 'Product Category 4', table_header)
        ws.write('AM5', 'Is Not A Sales Transaction', table_header)
        ws.write('AN5', 'Discount Name', table_header)
        ws.write('AO5', 'Discount Category 1', table_header)
        ws.write('AP5', 'Discount Category 2', table_header)
        ws.write('AQ5', 'Discount Category 3', table_header)
        ws.write('AR5', 'Discount Category 4', table_header)
        #ws.write('AS5', 'Unit Price', table_header)
        ws.write('AS5', 'Total Before Discount', table_header)
        ws.write('AT5', 'Discount', table_header)
        ws.write('AU5', 'Total After Discount', table_header)
        ws.write('AV5', 'Tax Before Discount', table_header)
        ws.write('AW5', 'Tax On Discount', table_header)
        ws.write('AX5', 'Tax After Discount', table_header)
        ws.write('AY5', 'Total Sales', table_header)
        ws.write('AZ5', 'Net Total', table_header)
        ws.write('BA5', 'Sale Date', table_header)
        ws.write('BB5', 'Not A Transaction', table_header)

        # FILL DATA
        def cutoff_time(date):
            # Convert from GMT+8 to UTC then cutoff 5 hours
            date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT) - timedelta(hours=3)
            return date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

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
                        ws.write('D%s' % row, prev_line['parent_area'], table_row_left)
                        ws.write('E%s' % row, prev_line['region'], table_row_left)
                        ws.write('F%s' % row, prev_line['asset_type'], table_row_left)
                        ws.write('G%s' % row, prev_line['location_type'], table_row_left)
                        ws.write('H%s' % row, prev_line['outlet_type'], table_row_left)
                        ws.write('I%s' % row, prev_line['outlet_status'], table_row_left)
                        ws.write('J%s' % row, prev_line['regional_manager'], table_row_left)
                        ws.write('K%s' % row, prev_line['area_manager'], table_row_left)
                        ws.write('L%s' % row, prev_line['pic1'], table_row_left)
                        ws.write('M%s' % row, prev_line['pic2'], table_row_left)
                        ws.write('N%s' % row, prev_line['pic3'], table_row_left)
                        ws.write('O%s' % row, prev_line['sale_person'], table_row_left)
                        ws.write('P%s' % row, prev_line['session_name'], table_row_left)
                        start_at = self.convert_timezone(prev_line['start_at'])
                        # start_at = self.convert_timezone('UTC', self.env.user.tz, line['start_at'])
                        ws.write_datetime('Q%s' % row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"),
                                          table_row_datetime)
                        if prev_line['stop_at']:
                            stop_at = self.convert_timezone(prev_line['stop_at'])
                            ws.write_datetime('R%s' % row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"),
                                              table_row_datetime)
                        else:
                            stop_at = ""
                            ws.write('R%s' % row, stop_at, table_row_left)
                        # FIXME: Duplicate column ?
                        ws.write('S%s' % row, prev_line['sale_person'], table_row_left)
                        date_order = self.convert_timezone('%s %s' % (prev_line['order_date'], prev_line['order_time']))
                        ws.write_datetime('T%s' % row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"),
                                          table_row_date)
                        ws.write_datetime('U%s' % row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"),
                                          table_row_time)
                        ws.write('V%s' % row, prev_line['order_ref'], table_row_left)
                        ws.write('W%s' % row, prev_line['invoice_no'], table_row_left)
                        ws.write('X%s' % row, prev_line['pos_reference'], table_row_left)
                        ws.write('Y%s' % row, prev_line['customer_name'], table_row_left)

                        ws.write('Z%s' % row, '', table_row_left)
                        ws.write('AA%s' % row, adjustment['adjustment_name'], table_row_left)
                        ws.write('AB%s' % row, '', table_row_left)
                        ws.write('AC%s' % row, '', table_row_left)
                        ws.write('AD%s' % row, '', table_row_left)
                        ws.write('AE%s' % row, '', table_row_left)

                        ws.write('AF%s' % row, '', table_row_left)
                        ws.write('AG%s' % row, '', table_row_left)
                        ws.write('AH%s' % row, '', table_row_left)
                        ws.write('AI%s' % row, '', table_row_left)
                        ws.write('AJ%s' % row, '', table_row_left)
                        ws.write('AK%s' % row, '', table_row_left)
                        ws.write('AL%s' % row, '', table_row_left)
                        ws.write('AM%s' % row, prev_line['non_sale'], table_row_left)

                        ws.write('AN%s' % promotion_row, '', table_row_left)
                        ws.write('AO%s' % promotion_row, '', table_row_left)
                        ws.write('AP%s' % promotion_row, '', table_row_left)
                        ws.write('AQ%s' % promotion_row, '', table_row_left)
                        ws.write('AR%s' % promotion_row, '', table_row_left)

                        if adjustment['adjustment_name'] == "Tax Adjustment":
                            ws.write('AS%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                            ws.write('AT%s' % row, 0, table_row_right)
                            ws.write('AU%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                            ws.write('AV%s' % row, 0, table_row_right)
                            ws.write('AW%s' % row, 0, table_row_right)
                            ws.write('AX%s' % row, adjustment['gst_after_discount'], table_row_right)
                            ws.write('AY%s' % row, 0, table_row_right)
                            ws.write('AZ%s' % row, adjustment['gst_after_discount']* -1, table_row_right)
                        elif adjustment['adjustment_name'] == "Price Rounding":
                            ws.write('AS%s' % row, adjustment['price_with_tax'], table_row_right)
                            ws.write('AT%s' % row, 0, table_row_right)
                            ws.write('AU%s' % row, adjustment['price_with_tax'], table_row_right)
                            ws.write('AV%s' % row, adjustment['tax'], table_row_right)
                            ws.write('AW%s' % row, 0, table_row_right)
                            ws.write('AX%s' % row, adjustment['tax'], table_row_right)
                            ws.write('AY%s' % row, adjustment['price_with_tax'] + adjustment['tax'], table_row_right)
                            ws.write('AZ%s' % row, adjustment['price_with_tax'], table_row_right)
                        elif adjustment['adjustment_name'] == "Bill Rounding":
                            ws.write('AS%s' % row, 0, table_row_right)
                            ws.write('AT%s' % row, 0, table_row_right)
                            ws.write('AU%s' % row, 0, table_row_right)
                            ws.write('AV%s' % row, 0, table_row_right)
                            ws.write('AW%s' % row, 0, table_row_right)
                            ws.write('AX%s' % row, 0, table_row_right)
                            ws.write('AY%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                            ws.write('AZ%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                        elif adjustment['adjustment_name'] == "Discount/TaxVar":
                            total_dicount_variance = (adjustment['total_discount_line'] or 0) - total_discount_product_line
                            discount_tax_variance = (adjustment['total_discount_line_tax'] or 0) - total_discount_product_line_tax
                            ws.write('AS%s' % row, 0, table_row_right)
                            ws.write('AT%s' % row, total_dicount_variance , table_row_right)
                            ws.write('AU%s' % row, total_dicount_variance , table_row_right)
                            ws.write('AV%s' % row, 0, table_row_right)
                            ws.write('AW%s' % row, discount_tax_variance, table_row_right)
                            ws.write('AX%s' % row, discount_tax_variance, table_row_right)
                            ws.write('AY%s' % row, total_dicount_variance + discount_tax_variance, table_row_right)
                            ws.write('AZ%s' % row, total_dicount_variance, table_row_right)

                        ws.write_datetime('BA%s' % row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
                        ws.write('BB%s' % row, any([prev_line['non_sale'], prev_line['is_refund'], prev_line['is_refunded']]) and 'YES' or 'NO', table_row_left)
                        row += 1
                order_ref = line['order_ref']
                total_discount_product_line = 0
                total_discount_product_line_tax = 0

            prev_line = line
            ws.write('A%s' % row, line['outlet'], table_row_left)
            ws.write('B%s' % row, line['outlet_code'], table_row_left)
            ws.write('C%s' % row, line['analytic_account'], table_row_left)
            ws.write('D%s' % row, line['parent_area'], table_row_left)
            ws.write('E%s' % row, line['region'], table_row_left)
            ws.write('F%s' % row, line['asset_type'], table_row_left)
            ws.write('G%s' % row, line['location_type'], table_row_left)
            ws.write('H%s' % row, line['outlet_type'], table_row_left)
            ws.write('I%s' % row, line['outlet_status'], table_row_left)
            ws.write('J%s' % row, line['regional_manager'], table_row_left)
            ws.write('K%s' % row, line['area_manager'], table_row_left)
            ws.write('L%s' % row, line['pic1'], table_row_left)
            ws.write('M%s' % row, line['pic2'], table_row_left)
            ws.write('N%s' % row, line['pic3'], table_row_left)
            ws.write('O%s' % row, line['sale_person'], table_row_left)
            ws.write('P%s' % row, line['session_name'], table_row_left)
            start_at = self.convert_timezone(line['start_at'])
            # start_at = self.convert_timezone('UTC', self.env.user.tz, line['start_at'])
            ws.write_datetime('Q%s' % row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
            if line['stop_at']:
                stop_at = self.convert_timezone(line['stop_at'])
                ws.write_datetime('R%s' % row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
            else:
                stop_at = ""
                ws.write('R%s' % row, stop_at, table_row_left)
            # FIXME: Duplicate column ?
            ws.write('S%s' % row, line['sale_person'], table_row_left)
            date_order = self.convert_timezone('%s %s' % (line['order_date'], line['order_time']))
            ws.write_datetime('T%s' % row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
            ws.write_datetime('U%s' % row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"), table_row_time)
            ws.write('V%s' % row, line['order_ref'], table_row_left)
            ws.write('W%s' % row, line['invoice_no'], table_row_left)
            ws.write('X%s' % row, line['pos_reference'], table_row_left)
            ws.write('Y%s' % row, line['customer_name'], table_row_left)
            ws.write('Z%s' % row, line['menu_number'], table_row_left)
            ws.write('AA%s' % row, line['menu_name'], table_row_left)
            menu_categ_name = line['menu_categ'].split("/") if line['menu_categ'] else ""
            categ_len = len(menu_categ_name)
            ws.write('AB%s' % row, menu_categ_name[0].strip() if categ_len > 0 else "", table_row_left)
            ws.write('AC%s' % row, menu_categ_name[1].strip() if categ_len > 1 else "", table_row_left)
            ws.write('AD%s' % row, menu_categ_name[2].strip() if categ_len > 2 else "", table_row_left)
            ws.write('AE%s' % row, menu_categ_name[3].strip() if categ_len > 3 else "", table_row_left)

            ws.write('AF%s' % row, line['product_name'], table_row_left)
            ws.write('AG%s' % row, line['product_quantity'], table_row_left)
            ws.write('AH%s' % row, line['uom_name'], table_row_left)
            prod_categ = line['product_category'].split("/") if line['product_category'] else ""
            prod_categ_len = len(prod_categ)
            ws.write('AI%s' % row, prod_categ[0] if prod_categ_len > 0 else "", table_row_left)
            ws.write('AJ%s' % row, prod_categ[1] if prod_categ_len > 1 else "", table_row_left)
            ws.write('AK%s' % row, prod_categ[2] if prod_categ_len > 2 else "", table_row_left)
            ws.write('AL%s' % row, prod_categ[3] if prod_categ_len > 3 else "", table_row_left)
            ws.write('AM%s' % row, line['non_sale'], table_row_left)

            promotion_row = row
            if line['promotions']:
                promotions = line['promotions'].split("|")
                for p in promotions:
                    p_data = p.split('###')
                    p_name = p_data[0]
                    p_categ = p_data[1].split("/")
                    promotion_categ_len = len(p_categ)
                    if p_name:
                        # Bind promotion data
                        ws.write('AN%s' % promotion_row, p_name, table_row_left)
                        ws.write('AO%s' % promotion_row, p_categ[0] if promotion_categ_len > 0 else "",
                                 table_row_left)
                        ws.write('AP%s' % promotion_row, p_categ[1] if promotion_categ_len > 1 else "",
                                 table_row_left)
                        ws.write('AQ%s' % promotion_row, p_categ[2] if promotion_categ_len > 2 else "",
                                 table_row_left)
                        ws.write('AR%s' % promotion_row, p_categ[3] if promotion_categ_len > 3 else "",
                                 table_row_left)
                        promotion_row += 1
                    else:
                        ws.write('AN%s' % promotion_row, '', table_row_left)
                        ws.write('AO%s' % promotion_row, '', table_row_left)
                        ws.write('AP%s' % promotion_row, '', table_row_left)
                        ws.write('AQ%s' % promotion_row, '', table_row_left)
                        ws.write('AR%s' % promotion_row, '', table_row_left)


            # Total Before Discount (A1)
            ws.write('AS%s' % row, line['amount_w_tax'], table_row_right)
            # Discount(A2)
            ws.write('AT%s' % row, -1 * (line['discount_amount'] or 0), table_row_right)
            total_discount_product_line += -1 * (line['discount_amount'] or 0)
            # Total After Discount (A3)
            total_after_discount = (line['amount_w_tax'] or 0) - (line['discount_amount'] or 0)
            ws.write('AU%s' % row, total_after_discount, table_row_right)
            # GST on A1 (B1)
            ws.write('AV%s' % row, line['tax'] or 0, table_row_right)

            # GST on A2 (B2)
            ws.write('AW%s' % row, -1 * (line['tax_discount'] or 0), table_row_right)
            total_discount_product_line_tax += -1 * (line['tax_discount'] or 0)
            # GST on A3 (B3)
            ws.write('AX%s' % row, (line['tax'] or 0) - (line['tax_discount'] or 0), table_row_right)

            # Total sale
            ws.write('AY%s' % row, total_after_discount + (line['tax'] or 0) - (line['tax_discount'] or 0), table_row_right)

            # Nett Total (A3-B3)
            ws.write('AZ%s' % row, total_after_discount, table_row_right)

            sale_date = self.convert_timezone('%s %s' % (line['order_date'], line['order_time']))
            sale_date = datetime.strptime(sale_date, '%Y-%m-%d %H:%M:%S')
            if sale_date.hour < 5:
                sale_date = sale_date - timedelta(hours=5)
            ws.write_datetime('BA%s' % row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
            ws.write('BB%s' % row, any([line['non_sale'], line['is_refund'], line['is_refunded']]) and 'YES' or 'NO', table_row_left)
            row += (promotion_row - row) + 1 if promotion_row == row else (promotion_row - row)
        else:
            if order_ref in adjustment_lines:
                # Write adjustment line per each order
                for adjustment in adjustment_lines[order_ref]:
                    ws.write('A%s' % row, prev_line['outlet'], table_row_left)
                    ws.write('B%s' % row, prev_line['outlet_code'], table_row_left)
                    ws.write('C%s' % row, prev_line['analytic_account'], table_row_left)
                    ws.write('D%s' % row, prev_line['parent_area'], table_row_left)
                    ws.write('E%s' % row, prev_line['region'], table_row_left)
                    ws.write('F%s' % row, prev_line['asset_type'], table_row_left)
                    ws.write('G%s' % row, prev_line['location_type'], table_row_left)
                    ws.write('H%s' % row, prev_line['outlet_type'], table_row_left)
                    ws.write('I%s' % row, prev_line['outlet_status'], table_row_left)
                    ws.write('J%s' % row, prev_line['regional_manager'], table_row_left)
                    ws.write('K%s' % row, prev_line['area_manager'], table_row_left)
                    ws.write('L%s' % row, prev_line['pic1'], table_row_left)
                    ws.write('M%s' % row, prev_line['pic2'], table_row_left)
                    ws.write('N%s' % row, prev_line['pic3'], table_row_left)
                    ws.write('O%s' % row, prev_line['sale_person'], table_row_left)
                    ws.write('P%s' % row, prev_line['session_name'], table_row_left)
                    start_at = self.convert_timezone(prev_line['start_at'])
                    # start_at = self.convert_timezone('UTC', self.env.user.tz, line['start_at'])
                    ws.write_datetime('Q%s' % row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"),
                                      table_row_datetime)
                    if prev_line['stop_at']:
                        stop_at = self.convert_timezone(prev_line['stop_at'])
                        ws.write_datetime('R%s' % row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"),
                                          table_row_datetime)
                    else:
                        stop_at = ""
                        ws.write('R%s' % row, stop_at, table_row_left)
                    # FIXME: Duplicate column ?
                    ws.write('S%s' % row, prev_line['sale_person'], table_row_left)
                    date_order = self.convert_timezone('%s %s' % (prev_line['order_date'], prev_line['order_time']))
                    ws.write_datetime('T%s' % row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"),
                                      table_row_date)
                    ws.write_datetime('U%s' % row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"),
                                      table_row_time)
                    ws.write('V%s' % row, prev_line['order_ref'], table_row_left)
                    ws.write('W%s' % row, prev_line['invoice_no'], table_row_left)
                    ws.write('X%s' % row, prev_line['pos_reference'], table_row_left)
                    ws.write('Y%s' % row, prev_line['customer_name'], table_row_left)

                    ws.write('Z%s' % row, '', table_row_left)
                    ws.write('AA%s' % row, adjustment['adjustment_name'], table_row_left)
                    ws.write('AB%s' % row, '', table_row_left)
                    ws.write('AC%s' % row, '', table_row_left)
                    ws.write('AD%s' % row, '', table_row_left)
                    ws.write('AE%s' % row, '', table_row_left)

                    ws.write('AF%s' % row, '', table_row_left)
                    ws.write('AG%s' % row, '', table_row_left)
                    ws.write('AH%s' % row, '', table_row_left)
                    ws.write('AI%s' % row, '', table_row_left)
                    ws.write('AJ%s' % row, '', table_row_left)
                    ws.write('AK%s' % row, '', table_row_left)
                    ws.write('AL%s' % row, '', table_row_left)
                    ws.write('AM%s' % row, prev_line['non_sale'], table_row_left)

                    ws.write('AN%s' % promotion_row, '', table_row_left)
                    ws.write('AO%s' % promotion_row, '', table_row_left)
                    ws.write('AP%s' % promotion_row, '', table_row_left)
                    ws.write('AQ%s' % promotion_row, '', table_row_left)
                    ws.write('AR%s' % promotion_row, '', table_row_left)

                    if adjustment['adjustment_name'] == "Tax Adjustment":
                        ws.write('AS%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                        ws.write('AT%s' % row, 0, table_row_right)
                        ws.write('AU%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                        ws.write('AV%s' % row, 0, table_row_right)
                        ws.write('AW%s' % row, 0, table_row_right)
                        ws.write('AX%s' % row, adjustment['gst_after_discount'], table_row_right)
                        ws.write('AY%s' % row, 0, table_row_right)
                        ws.write('AZ%s' % row, adjustment['gst_after_discount'] * -1, table_row_right)
                    elif adjustment['adjustment_name'] == "Price Rounding":
                        ws.write('AS%s' % row, adjustment['price_with_tax'], table_row_right)
                        ws.write('AT%s' % row, 0, table_row_right)
                        ws.write('AU%s' % row, adjustment['price_with_tax'], table_row_right)
                        ws.write('AV%s' % row, adjustment['tax'], table_row_right)
                        ws.write('AW%s' % row, 0, table_row_right)
                        ws.write('AX%s' % row, adjustment['tax'], table_row_right)
                        ws.write('AY%s' % row, adjustment['price_with_tax'] + adjustment['tax'], table_row_right)
                        ws.write('AZ%s' % row, adjustment['price_with_tax'], table_row_right)
                    elif adjustment['adjustment_name'] == "Bill Rounding":
                        ws.write('AS%s' % row, 0, table_row_right)
                        ws.write('AT%s' % row, 0, table_row_right)
                        ws.write('AU%s' % row, 0, table_row_right)
                        ws.write('AV%s' % row, 0, table_row_right)
                        ws.write('AW%s' % row, 0, table_row_right)
                        ws.write('AX%s' % row, 0, table_row_right)
                        ws.write('AY%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                        ws.write('AZ%s' % row, adjustment['payment_amount'] * -1, table_row_right)
                    elif adjustment['adjustment_name'] == "Discount/TaxVar":
                        total_dicount_variance = (adjustment['total_discount_line'] or 0) - total_discount_product_line
                        discount_tax_variance = (adjustment[
                                                     'total_discount_line_tax'] or 0) - total_discount_product_line_tax
                        ws.write('AS%s' % row, 0, table_row_right)
                        ws.write('AT%s' % row, total_dicount_variance, table_row_right)
                        ws.write('AU%s' % row, total_dicount_variance, table_row_right)
                        ws.write('AV%s' % row, 0, table_row_right)
                        ws.write('AW%s' % row, discount_tax_variance, table_row_right)
                        ws.write('AX%s' % row, discount_tax_variance, table_row_right)
                        ws.write('AY%s' % row, total_dicount_variance + discount_tax_variance, table_row_right)
                        ws.write('AZ%s' % row, total_dicount_variance, table_row_right)

                    ws.write_datetime('BA%s' % row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
                    ws.write('BB%s' % row, any(
                        [prev_line['non_sale'], prev_line['is_refund'], prev_line['is_refunded']]) and 'YES' or 'NO',
                             table_row_left)
                    row += 1

    # TODO: Optimize this query and remove duplicate outlet where conditions
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
          --  GET INFORMATION FROM ORDER LINES
          --  DISCOUNT AMOUNT IS NOT INCLUDED IN ORDER'S AMOUNT TOTAL
          --  PRICE UNIT IS TAX INCLUDED, SO AMOUNT TOTAL HERE IS TAX INCLUDED ALSO
            order_line_tmp AS (
              SELECT
                pol.order_id,
                pol_master.name                                                                  AS menu_number,
                product_master.name_template                                                     AS menu_name,
                menu_categ.complete_name                                                         AS menu_categ,
                product.name_template                                                            AS product_name,
                pol.qty                                                                          AS product_quantity,
                uom.name                                                                         AS uom_name,
                prod_categ.complete_name                                                         AS product_category,
                pol.non_sale,
                string_agg(DISTINCT concat(promotion.name, '###', promotion_categ.complete_name), '|') AS promotions,
                ROUND(pol.price_unit, 2)                                                         AS price_unit,
                CASE WHEN coalesce(tax.price_include,false) = TRUE 
				    THEN
					    pol.discount_amount -  pol.discount_amount / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100)
				    ELSE
					    pol.discount_amount
				    END
			    AS discount_amount,
                
                CASE WHEN coalesce(tax.price_include,false) = TRUE 
				THEN
					ROUND( ROUND(pol.qty * pol.price_unit, 2) -  ROUND( ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100),2), 2)  																
				ELSE
					ROUND(pol.qty * pol.price_unit, 2)
				END
			    AS amount_w_tax,
                ROUND(ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2) AS tax,
                ROUND(pol.discount_amount / (1 + CASE WHEN coalesce(tax.price_include,false) = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2) AS tax_discount,
                coalesce(tax.price_include,false) as price_include
              FROM pos_order po
                LEFT JOIN pos_order_line pol ON po.id = pol.order_id AND pol.product_id != {rounding_product_id}
                LEFT JOIN product_product product ON pol.product_id = product.id
                LEFT JOIN pos_order_line_promotion_default_rel rel ON pol.id = rel.pos_order_line_id
                LEFT JOIN br_bundle_promotion promotion ON rel.promotion_id = promotion.id
                LEFT JOIN br_promotion_category promotion_categ ON promotion.promotion_category_id = promotion_categ.id
                LEFT JOIN _get_pos_order_line_tax(pol.id) tax ON tax.pol_id = pol.id
                LEFT JOIN promotion_products ON promotion_products.order_id = po.id
                LEFT JOIN br_pos_order_line_master pol_master ON pol.master_id = pol_master.id
                LEFT JOIN product_product product_master ON pol_master.product_id = product_master.id
                LEFT JOIN br_menu_category menu_categ ON product_master.menu_category_id = menu_categ.id
                LEFT JOIN product_template p_template ON product.product_tmpl_id = p_template.id
                LEFT JOIN product_uom uom ON p_template.uom_id = uom.id
                LEFT JOIN product_category prod_categ ON p_template.categ_id = prod_categ.id
              WHERE
                po.outlet_id IN
                    (SELECT br_multi_outlet_outlet_id
                     FROM br_multi_outlet_outlet_res_users_rel brrel
                     WHERE brrel.res_users_id = {user_id_report}
                     )
                AND {sql_oulet_string}
                AND po.date_order >= '{start_date}'
                AND po.date_order <= '{end_date}'
                AND pol.product_id NOT IN
                    (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
            GROUP BY pol.id, product_master.id, menu_categ.id, product.id, uom.id,
            prod_categ.id, tax.amount, pol_master.id, tax.price_include

          )
        SELECT
          --   MAIN INFOMATION
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
          -- ORDERLINE INFORMATION
          order_line_tmp.price_include,
          order_line_tmp.menu_number,
          order_line_tmp.menu_name,
          order_line_tmp.menu_categ,
          order_line_tmp.product_name,
          order_line_tmp.product_quantity,
          order_line_tmp.uom_name,
          order_line_tmp.product_category,
          order_line_tmp.non_sale,
          order_line_tmp.promotions,
          order_line_tmp.price_unit,
          order_line_tmp.discount_amount,
          order_line_tmp.amount_w_tax,
          order_line_tmp.tax,
          order_line_tmp.tax_discount
        FROM pos_order po
          LEFT JOIN get_history_outlet(po.outlet_id, po.date_order) ho ON po.outlet_id = ho.o_id
          INNER JOIN br_multi_outlet_outlet bmoo ON po.outlet_id = bmoo.id
          LEFT JOIN account_analytic_account aaa ON bmoo.analytic_account_id = aaa.id
          LEFT JOIN res_country_state rct ON ho.area = rct.id
          LEFT JOIN res_country_state rct_1 ON rct.parent_id = rct_1.id
          LEFT JOIN br_multi_outlet_region_area region ON region.id = ho.region
          LEFT JOIN br_multi_outlet_outlet_type outlet_type ON outlet_type.id = ho.asset_type
          LEFT JOIN br_multi_outlet_outlet_type outlet_type_1 ON outlet_type_1.id = ho.location_type
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
          LEFT JOIN order_line_tmp ON order_line_tmp.order_id = po.id
        WHERE
          po.outlet_id IN
              (
              SELECT br_multi_outlet_outlet_id
               FROM br_multi_outlet_outlet_res_users_rel brrel
               WHERE brrel.res_users_id = {user_id_report}
               )
          AND {sql_oulet_string}
          AND po.date_order >= '{start_date}'
          AND po.date_order <= '{end_date}'
          ORDER BY bmoo.name, ps.start_at, po.pos_reference;
              '''.format(**args)

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




pos_order_report('report.br_point_of_sale.pos_order_report', 'pos.order.data')
