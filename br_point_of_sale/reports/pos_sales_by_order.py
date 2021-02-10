# --*-- coding: utf-8 --*--

from openerp import fields, models, api, registry, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz
from datetime import datetime, timedelta
from openerp.osv import fields as F
import logging
from report_tools import round_down

_logger = logging.getLogger(__name__)


DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class pos_sale_data(models.TransientModel):
    _name = 'pos.sale.data'

    start_date = fields.Date(string=_("Start date"))
    end_date = fields.Date(string=_("End date"))
    outlet_ids = fields.Many2many(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')

    _columns = {
        'user_id': F.many2one('res.users', 'User',
                              help="Person who uses the cash register. It can be a reliever, a student or an interim employee."),
    }

    _defaults = {
        'user_id': lambda self, cr, uid, context: uid,
    }

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_point_of_sale.pos_sale_report')


class pos_sale_report(ReportXlsx):
    _name = 'report.br_point_of_sale.pos_sale_report'

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

    def bind_data(self, row, report_data):
        pass

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
        # ws.set_column(0, 0, 30)
        # col_width = {
        #     30: range(0, 41)
        # }
        # for w in col_width:
        #     for c in col_width[w]:
        ws.set_column(0, 45, 30)
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
        ws.write('AA5', 'Is Not A Sales Transaction', table_header)
        ws.write('AB5', 'Staff Redeemed', table_header)
        ws.write('AC5', 'Remark', table_header)
        ws.write('AD5', 'Voucher code', table_header)
        ws.write('AE5', 'Discount Name', table_header)
        ws.write('AF5', 'Discount Category 1', table_header)
        ws.write('AG5', 'Discount Category 2', table_header)
        ws.write('AH5', 'Discount Category 3', table_header)
        ws.write('AI5', 'Discount Category 4', table_header)
        ws.write('AJ5', 'Payment Method', table_header)
        ws.write('AK5', 'Payment Amount', table_header)
        ws.write('AL5', 'Total Before Discount', table_header)
        ws.write('AM5', 'Discount', table_header)
        ws.write('AN5', 'Total After Discount', table_header)
        ws.write('AO5', 'Tax Before Discount', table_header)
        ws.write('AP5', 'Tax On Discount', table_header)
        ws.write('AQ5', 'Tax After Discount', table_header)
        ws.write('AR5', 'Net Total', table_header)
        ws.write('AS5', 'On site Sales', table_header)
        ws.write('AT5', 'Off site Sales', table_header)
        ws.write('AU5', 'Redemption Sales', table_header)
        ws.write('AV5', 'Sale Date', table_header)
        ws.write('AW5', 'Not A Transaction', table_header)

        user_id_report = report.user_id.id
        start_date = report.start_date + ' 00:00:00'
        start_date = datetime.strptime(start_date, DATE_FORMAT) - timedelta(hours=3)
        start_date = start_date.strftime(DATE_FORMAT)
        utc_start_date = start_date

        end_date = report.end_date + ' 23:59:59'
        end_date = datetime.strptime(end_date, DATE_FORMAT) - timedelta(hours=3)
        end_date = end_date.strftime(DATE_FORMAT)
        utc_end_date = end_date

        sql_oulet_string = '1=1'
        if outlet_ids:
            sql_oulet_string = 'po.outlet_id in ' + str(outlet_ids).replace('[', '(').replace(']', ')')

        credentials = {
            'user_id_report': user_id_report,
            'sql_oulet_string': sql_oulet_string,
            'start_date': utc_start_date,
            'end_date': utc_end_date
        }

        report_data = self.get_report_data(credentials)
        row = 6
        # FILL DATA
        for line in report_data:
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
            ws.write('AA%s' % row, line['non_sale'], table_row_left)

            ws.write('AB%s' % row, line['staff_redeemed'], table_row_left)
            ws.write('AC%s' % row, line['remark'], table_row_left)


            promotion_row = row
            taken_rows = [row]
            if line['promotions']:
                promotions = line['promotions'].split("|")
                # if len(promotions) > 1:
                for p in promotions:
                    p_data = p.split('###')
                    p_name = p_data[0]
                    p_categ = p_data[1].split("/")
                    p_voucher_code = p_data[2]
                    promotion_categ_len = len(p_categ)
                    if p_name:
                        # Print blank cell for order have multiple promotions
                        if promotion_row > row:
                            ws.write('A%s' % promotion_row, line['outlet'], table_row_left)
                            ws.write('B%s' % promotion_row, line['outlet_code'], table_row_left)
                            ws.write('C%s' % promotion_row, line['analytic_account'], table_row_left)
                            ws.write('D%s' % promotion_row, line['area'], table_row_left)
                            ws.write('E%s' % promotion_row, line['parent_area'], table_row_left)
                            ws.write('F%s' % promotion_row, line['region'], table_row_left)
                            ws.write('G%s' % promotion_row, line['asset_type'], table_row_left)
                            ws.write('H%s' % promotion_row, line['location_type'], table_row_left)
                            ws.write('I%s' % promotion_row, line['outlet_type'], table_row_left)
                            ws.write('J%s' % promotion_row, line['outlet_status'], table_row_left)
                            ws.write('K%s' % promotion_row, line['regional_manager'], table_row_left)
                            ws.write('L%s' % promotion_row, line['area_manager'], table_row_left)
                            ws.write('M%s' % promotion_row, line['pic1'], table_row_left)
                            ws.write('N%s' % promotion_row, line['pic2'], table_row_left)
                            ws.write('O%s' % promotion_row, line['pic3'], table_row_left)
                            ws.write('P%s' % promotion_row, line['sale_person'], table_row_left)
                            ws.write('Q%s' % promotion_row, line['session_name'], table_row_left)
                            ws.write_datetime('R%s' % promotion_row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                            if line['stop_at']:
                                ws.write_datetime('S%s' % promotion_row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                            else:
                                ws.write('S%s' % promotion_row, stop_at, table_row_left)
                            ws.write('T%s' % promotion_row, line['sale_person'], table_row_left)
                            ws.write_datetime('U%s' % promotion_row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
                            ws.write_datetime('V%s' % promotion_row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"), table_row_time)
                            ws.write('W%s' % promotion_row, line['order_ref'], table_row_left)
                            ws.write('X%s' % promotion_row, line['invoice_no'], table_row_left)
                            ws.write('Y%s' % promotion_row, line['pos_reference'], table_row_left)
                            ws.write('Z%s' % promotion_row, line['customer_name'], table_row_left)
                            ws.write('AA%s' % promotion_row, line['non_sale'], table_row_left)
                            ws.write('AB%s' % promotion_row, line['staff_redeemed'], table_row_left)
                            ws.write('AC%s' % promotion_row, line['remark'], table_row_left)

                            ws.write('AJ%s' % promotion_row, '', table_row_left)
                            ws.write('AK%s' % promotion_row, 0, table_row_right)
                            ws.write('AL%s' % promotion_row, 0, table_row_right)
                            ws.write('AM%s' % promotion_row, 0, table_row_right)
                            ws.write('AN%s' % promotion_row, 0, table_row_right)
                            ws.write('AO%s' % promotion_row, 0, table_row_right)
                            ws.write('AP%s' % promotion_row, 0, table_row_right)
                            ws.write('AQ%s' % promotion_row, 0, table_row_right)
                            ws.write('AR%s' % promotion_row, 0, table_row_right)
                            ws.write('AS%s' % promotion_row, 0, table_row_right)
                            ws.write('AU%s' % promotion_row, 0, table_row_right)
                            ws.write('AT%s' % promotion_row, 0, table_row_right)
                            sale_date = self.convert_timezone('%s %s' % (line['order_date'], line['order_time']))
                            sale_date = datetime.strptime(sale_date, '%Y-%m-%d %H:%M:%S')
                            if sale_date.hour < 5:
                                sale_date = sale_date - timedelta(hours=5)
                            ws.write_datetime('AV%s' % promotion_row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
                            ws.write('AW%s' % promotion_row, 'YES', table_row_left)

                        # Bind promotion data
                        ws.write('AD%s' % promotion_row, p_voucher_code, table_row_left)
                        ws.write('AE%s' % promotion_row, p_name, table_row_left)
                        ws.write('AF%s' % promotion_row, p_categ[0] if promotion_categ_len > 0 else "",
                                 table_row_left)
                        ws.write('AG%s' % promotion_row, p_categ[1] if promotion_categ_len > 1 else "",
                                 table_row_left)
                        ws.write('AH%s' % promotion_row, p_categ[2] if promotion_categ_len > 2 else "",
                                 table_row_left)
                        ws.write('AI%s' % promotion_row, p_categ[3] if promotion_categ_len > 3 else "",
                                 table_row_left)
                        taken_rows.append(promotion_row)
                        promotion_row += 1
                    else:
                        ws.write('AD%s' % promotion_row, '', table_row_left)
                        ws.write('AE%s' % promotion_row, '', table_row_left)
                        ws.write('AF%s' % promotion_row, '', table_row_left)
                        ws.write('AG%s' % promotion_row, '', table_row_left)
                        ws.write('AH%s' % promotion_row, '', table_row_left)
                        ws.write('AI%s' % promotion_row, '', table_row_left)

            payment_row = row
            if line['payment_str']:
                payments = line['payment_str'].split("|")
                payment_types = line['payment_type_str'].split('|')
                for pm in payments:
                    pm_data = pm.split(",")
                    if len(pm_data) > 1 :
                        # Print basic information for payment rows
                        if payment_row not in taken_rows:
                            ws.write('A%s' % payment_row, line['outlet'], table_row_left)
                            ws.write('B%s' % payment_row, line['outlet_code'], table_row_left)
                            ws.write('C%s' % payment_row, line['analytic_account'], table_row_left)
                            ws.write('D%s' % payment_row, line['area'], table_row_left)
                            ws.write('E%s' % payment_row, line['parent_area'], table_row_left)
                            ws.write('F%s' % payment_row, line['region'], table_row_left)
                            ws.write('G%s' % payment_row, line['asset_type'], table_row_left)
                            ws.write('H%s' % payment_row, line['location_type'], table_row_left)
                            ws.write('I%s' % payment_row, line['outlet_type'], table_row_left)
                            ws.write('J%s' % payment_row, line['outlet_status'], table_row_left)
                            ws.write('K%s' % payment_row, line['regional_manager'], table_row_left)
                            ws.write('L%s' % payment_row, line['area_manager'], table_row_left)
                            ws.write('M%s' % payment_row, line['pic1'], table_row_left)
                            ws.write('N%s' % payment_row, line['pic2'], table_row_left)
                            ws.write('O%s' % payment_row, line['pic3'], table_row_left)
                            ws.write('P%s' % payment_row, line['sale_person'], table_row_left)
                            ws.write('Q%s' % payment_row, line['session_name'], table_row_left)
                            ws.write_datetime('R%s' % payment_row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                            if line['stop_at']:
                                ws.write_datetime('S%s' % payment_row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                            else:
                                ws.write('S%s' % payment_row, stop_at, table_row_left)
                            ws.write('T%s' % payment_row, line['sale_person'], table_row_left)
                            ws.write_datetime('U%s' % payment_row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
                            ws.write_datetime('V%s' % payment_row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"), table_row_time)
                            ws.write('W%s' % payment_row, line['order_ref'], table_row_left)
                            ws.write('X%s' % payment_row, line['invoice_no'], table_row_left)
                            ws.write('Y%s' % payment_row, line['pos_reference'], table_row_left)
                            ws.write('Z%s' % payment_row, line['customer_name'], table_row_left)
                            ws.write('AA%s' % payment_row, line['non_sale'], table_row_left)
                            ws.write('AB%s' % payment_row, line['staff_redeemed'], table_row_left)
                            ws.write('AC%s' % payment_row, line['remark'], table_row_left)

                            # Reserve for promotion
                            ws.write('AD%s' % payment_row, '', table_row_left)
                            ws.write('AE%s' % payment_row, '', table_row_left)
                            ws.write('AF%s' % payment_row, '', table_row_left)
                            ws.write('AG%s' % payment_row, '', table_row_left)
                            ws.write('AH%s' % payment_row, '', table_row_left)
                            ws.write('AI%s' % payment_row, '', table_row_left)

                            ws.write('AJ%s' % payment_row, 0, table_row_right)
                            ws.write('AK%s' % payment_row, 0, table_row_right)
                            ws.write('AL%s' % payment_row, 0, table_row_right)
                            ws.write('AM%s' % payment_row, 0, table_row_right)
                            ws.write('AN%s' % payment_row, 0, table_row_right)
                            ws.write('AO%s' % payment_row, 0, table_row_right)
                            ws.write('AP%s' % payment_row, 0, table_row_right)
                            ws.write('AQ%s' % payment_row, 0, table_row_right)
                            ws.write('AR%s' % payment_row, 0, table_row_right)
                            ws.write('AS%s' % payment_row, 0, table_row_right)
                            ws.write('AT%s' % payment_row, 0, table_row_right)
                            ws.write('AU%s' % payment_row, 0, table_row_right)
                            sale_date = self.convert_timezone('%s %s' % (line['order_date'], line['order_time']))
                            sale_date = datetime.strptime(sale_date, '%Y-%m-%d %H:%M:%S')
                            if sale_date.hour < 5:
                                sale_date = sale_date - timedelta(hours=5)
                            ws.write_datetime('AV%s' % payment_row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
                            ws.write('AW%s' % payment_row, 'YES', table_row_left)

                        pm_method = pm_data[0]
                        pm_amount = float(pm_data[1]) if pm_data[1].strip() else pm_data[1]
                        ws.write('AJ%s' % payment_row, pm_method, table_row_left)
                        ws.write('AK%s' % payment_row, pm_amount, table_row_right)
                        payment_row += 1

            # Total Before Discount (A1)
            ws.write('AL%s' % row, line['amount_w_tax'], table_row_right)
            # Discount(A2)
            ws.write('AM%s' % row, -1 * (line['discount_amount'] or 0), table_row_right)
            # Total After Discount (A3)
            total_after_discount = (line['amount_w_tax'] or 0) - (line['discount_amount'] or 0)
            ws.write('AN%s' % row, total_after_discount, table_row_right)
            # GST on A1 (B1)
            ws.write('AO%s' % row, line['tax'] or 0, table_row_right)
            # GST on A2 (B2)
            ws.write('AP%s' % row, -1 * (line['tax_discount'] or 0), table_row_right)
            # GST on A3 (B3)
            ws.write('AQ%s' % row, line['gst_after_discount'] or 0, table_row_right)
            # ws.write('AN%s' % row, (line['tax'] or 0) - (line['tax_discount'] or 0), table_row_right)
            # Nett Total (A3-B3)
            net_total = total_after_discount - (line['price_include'] and line['gst_after_discount'] or 0)
            ws.write('AR%s' % row, net_total, table_row_right)

            total_payment_on_site_type = 0
            total_payment_off_site_type = 0
            total_payment_redemption_site_type = 0
            total_all_type = 0
            for payment_type in payment_types:
                data = payment_type.split(',')
                if len(data) > 1:
                    try:
                        total_all_type += float(data[1])
                    except:
                        total_all_type += 0
                    if data[0] == 'on_site':
                        total_payment_on_site_type += float(data[1])
                    elif data[0] == 'off_site':
                        total_payment_off_site_type += float(data[1])
                    elif data[0] == 'redemption':
                        total_payment_redemption_site_type += float(data[1])

            payment_on_site = 0
            payment_off_site = 0
            payment_redemption_site = 0
            if total_all_type != 0:
                payment_on_site = total_payment_on_site_type / total_all_type * net_total
                payment_off_site = total_payment_off_site_type / total_all_type * net_total
                payment_redemption_site = total_payment_redemption_site_type / total_all_type * net_total

            ws.write('AS%s' % row, payment_on_site, table_row_right)
            ws.write('AT%s' % row, payment_off_site, table_row_right)
            ws.write('AU%s' % row, payment_redemption_site, table_row_right)

            # ws.write('AO%s' % row, total_after_discount - ((line['tax'] or 0) - (line['tax_discount'] or 0)), table_row_right)
            sale_date = self.convert_timezone('%s %s' % (line['order_date'], line['order_time']))
            sale_date = datetime.strptime(sale_date, '%Y-%m-%d %H:%M:%S')
            if sale_date.hour < 5:
                sale_date = sale_date - timedelta(hours=5)
            ws.write_datetime('AV%s' % row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)
            ws.write('AW%s' % row, any([line['non_sale'], line['is_refund'], line['is_refunded']]) and 'YES' or 'NO', table_row_left)

            _row = payment_row if payment_row > promotion_row else promotion_row
            row += (_row - row) + 1 if _row == row else (_row - row)


    def get_report_data(self, args):
        # TODO: Move get_history_outlet function to wizard
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
            WHERE po.outlet_id IN
                (SELECT br_multi_outlet_outlet_id
                 FROM br_multi_outlet_outlet_res_users_rel brrel
                 WHERE brrel.res_users_id = {user_id_report})
                AND {sql_oulet_string}
                AND po.date_order >= '{start_date}'
                AND po.date_order <= '{end_date}'
            GROUP BY po.id, pc.id
        ),
          promotion_tmp AS (
              SELECT
                pol.order_id,
                string_agg(DISTINCT concat(promotion.name, '###', promotion_categ.complete_name, '###', v.voucher_code), '|') AS promotions
              FROM pos_order po
                LEFT JOIN pos_order_line pol ON po.id = pol.order_id
                LEFT JOIN pos_order_line_promotion_default_rel rel ON pol.id = rel.pos_order_line_id
                LEFT JOIN br_bundle_promotion promotion ON rel.promotion_id = promotion.id
                LEFT JOIN br_promotion_category promotion_categ ON promotion.promotion_category_id = promotion_categ.id
                LEFT JOIN
                    (SELECT
                        po_voucher_rel.pos_order_id,
                        voucher.voucher_code,
                        voucher.promotion_id
                     FROM br_config_voucher_pos_order_rel po_voucher_rel
                       INNER JOIN br_config_voucher voucher ON po_voucher_rel.br_config_voucher_id = voucher.id
                    ) v ON po.id = v.pos_order_id AND v.promotion_id = promotion.id

              WHERE po.outlet_id IN
                      (SELECT br_multi_outlet_outlet_id
                       FROM br_multi_outlet_outlet_res_users_rel brrel
                       WHERE brrel.res_users_id = {user_id_report})
                      AND {sql_oulet_string}
                      AND po.date_order >= '{start_date}'
                      AND po.date_order <= '{end_date}'
              GROUP BY pol.order_id
          ),
        -- GET INFORMATION FROM ORDER LINES
            order_line_tmp AS (
              SELECT
                pol.order_id,
                pol.non_sale,
                SUM(CASE WHEN pol.product_id IN (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
                    THEN
                        ROUND(-1 * pol.qty * pol.price_unit, 2)
                    ELSE 0 END
                )                                                                        AS discount_amount,
                SUM(CASE WHEN pol.product_id NOT IN (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
                    THEN
                        ROUND(pol.qty * pol.price_unit, 2)
                    ELSE 0 END
                )                                                                        AS amount_w_tax,
                SUM(CASE WHEN pol.product_id NOT IN (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
                    THEN
                        ROUND(ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN tax.amount / 100 ELSE 0 END) * (tax.amount / 100), 2)
                    ELSE 0 END
                )  AS tax,
                SUM(CASE WHEN pol.product_id IN (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
                    THEN
                        ROUND(-1 * ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN tax.amount / 100 ELSE 0 END) * (tax.amount / 100), 2)
                    ELSE 0 END
                ) AS tax_discount,
                tax.price_include,
                string_agg(DISTINCT staff.display_name,'|')                                                                              AS staff_redeemed
              FROM pos_order po
                LEFT JOIN pos_order_line pol ON po.id = pol.order_id
                LEFT JOIN _get_pos_order_line_tax(pol.id) tax ON tax.pol_id = pol.id
                LEFT JOIN promotion_products ON promotion_products.order_id = po.id
                LEFT JOIN res_users ON pol.user_promotion = res_users.id
                LEFT JOIN res_partner staff ON res_users.partner_id = staff.id
              WHERE po.outlet_id IN
                      (SELECT br_multi_outlet_outlet_id
                       FROM br_multi_outlet_outlet_res_users_rel brrel
                       WHERE brrel.res_users_id = {user_id_report})
                      AND {sql_oulet_string}
                      AND po.date_order >= '{start_date}'
                      AND po.date_order <= '{end_date}'
              GROUP BY pol.order_id, pol.non_sale, tax.id, tax.amount, tax.price_include
          ),
            payment_line_tmp AS (
              SELECT
                tmp.order_id,
                string_agg(concat(tmp.payment_method, ', ', tmp.payment_amount), '|') AS payment_str
              FROM
                (
                  SELECT
                    po.id            AS order_id,
                    aj.name          AS payment_method,
                    SUM(absl.amount) AS payment_amount
                  FROM pos_order po
                    LEFT JOIN account_bank_statement_line absl ON po.id = absl.pos_statement_id
                    LEFT JOIN account_journal aj ON absl.journal_id = aj.id
                  WHERE po.outlet_id IN
                      (SELECT br_multi_outlet_outlet_id
                       FROM br_multi_outlet_outlet_res_users_rel brrel
                       WHERE brrel.res_users_id = {user_id_report})
                      AND {sql_oulet_string}
                      AND po.date_order >= '{start_date}'
                      AND po.date_order <= '{end_date}'
                  GROUP BY po.id, aj.id
                  ORDER BY SUM(absl.amount) DESC
                ) tmp
              GROUP BY tmp.order_id
            ),
            payment_line_by_type AS (
                SELECT
                    tmp.order_id,
                    string_agg(concat(tmp.payment_type, ', ', tmp.payment_amount), '|') AS payment_type_str
                  FROM
                    (
                      SELECT
                        po.id            AS order_id,
                        --aj.name          AS payment_method,
                                            aj.payment_type  AS payment_type,
                        SUM(absl.amount) AS payment_amount
                      FROM pos_order po
                        LEFT JOIN account_bank_statement_line absl ON po.id = absl.pos_statement_id
                        LEFT JOIN account_journal aj ON absl.journal_id = aj.id
                      WHERE po.outlet_id IN
                          (SELECT br_multi_outlet_outlet_id
                           FROM br_multi_outlet_outlet_res_users_rel brrel
                           WHERE brrel.res_users_id = {user_id_report})
                          AND {sql_oulet_string}
                          AND po.date_order >= '{start_date}'
                          AND po.date_order <= '{end_date}'
                      GROUP BY po.id, aj.payment_type
                      ORDER BY SUM(absl.amount) DESC
                    ) tmp
                  GROUP BY tmp.order_id
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
          promotion_tmp.promotions,
          order_line_tmp.discount_amount    AS                                        discount_amount,
          order_line_tmp.amount_w_tax + coalesce(po.tax_adjustment, 0) AS amount_w_tax,
          order_line_tmp.tax + coalesce(po.tax_adjustment, 0) AS tax,
          order_line_tmp.tax_discount,
          order_line_tmp.non_sale,
          order_line_tmp.price_include,
          order_line_tmp.tax + coalesce(po.tax_adjustment, 0) - order_line_tmp.tax_discount AS gst_after_discount,
          coalesce(po.tax_adjustment) as tax_adjustment,
          payment_line_tmp.payment_str,
          payment_line_by_type.payment_type_str,
          order_line_tmp.staff_redeemed,
          po.vouchers AS voucher_codes,
          po.note AS remark,
          po.is_refund,
          po.is_refunded
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
          LEFT JOIN payment_line_tmp ON payment_line_tmp.order_id = po.id
          LEFT JOIN payment_line_by_type ON payment_line_by_type.order_id = po.id
          LEFT JOIN promotion_tmp ON promotion_tmp.order_id = po.id
        WHERE po.outlet_id IN
            (SELECT br_multi_outlet_outlet_id
             FROM br_multi_outlet_outlet_res_users_rel brrel
             WHERE brrel.res_users_id = {user_id_report})
            AND {sql_oulet_string}
            AND po.date_order >= '{start_date}'
            AND po.date_order <= '{end_date}'
        ORDER BY bmoo.name, ps.start_at, po.pos_reference;
        '''.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_workbook_options(self):
        return {}


pos_sale_report('report.br_point_of_sale.pos_sale_report', 'pos.sale.data')