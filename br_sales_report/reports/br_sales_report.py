# --*-- coding: utf-8 --*--

from openerp import fields, models, api, registry, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
import pytz
from datetime import datetime, timedelta
from openerp.osv import fields as F
import logging

_logger = logging.getLogger(__name__)


DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
REPORTTYPE = {
    'tranc': "By Transaction",
    'outlet_day': "By Outlet by Day"
}
TRANSTYPE = {
    'all': "All",
    'sale': 'Sale',
    'nonsale': 'Non-Sale'
}

def colToExcel(col): # col is 1 based
    excelCol = str()
    div = col 
    while div:
        (div, mod) = divmod(div-1, 26) # will return (x, 0 .. 25)
        excelCol = chr(mod + 65) + excelCol

    return excelCol

def colNameToNum(name):
    pow = 1
    colNum = 0
    for letter in name[::-1]:
            colNum += (int(letter, 36) -9) * pow
            pow *= 26
    return colNum

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]

class br_sales_report(models.TransientModel):
    _name = 'br.sales.report'

    start_date = fields.Date(string=_("Start date"))
    end_date = fields.Date(string=_("End date"))
    outlet_ids = fields.Many2many(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')
    report_type = fields.Selection([('tranc', 'By Transaction'), ('outlet_day', 'By Outlet by Day')], string="Report Type", required=True)
    trans_type = fields.Selection([('all', 'All'), ('sale', 'Sale'), ('nonsale', 'Non-Sale')], string="Transaction Type", default="all")

    _columns = {
        'user_id': F.many2one('res.users', 'User',
                              help="Person who uses the cash register. It can be a reliever, a student or an interim employee."),
    }

    _defaults = {
        'user_id': lambda self, cr, uid, context: uid,
    }

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_sales_report.br_sales_order_report')

    @api.onchange('report_type')
    def _onchange_report_type(self):
        if self.report_type and self.report_type == 'outlet_day':
            self.trans_type = 'sale'


class br_sales_order_report(ReportXlsx):
    _name = 'report.br_sales_report.br_sales_order_report'

    def convert_timezone(self, from_tz, to_tz, date):
        from_tz = pytz.timezone(from_tz).localize(datetime.strptime(date, DATE_FORMAT))
        to_tz = from_tz.astimezone(pytz.timezone(to_tz))
        return to_tz.strftime(DATE_FORMAT)

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
            'border': 0,
            'font_name': 'Times New Roman',
        })
        table_row_left_1 = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'bold': 1,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })
        table_row_right_1 = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'bold': 1,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })

        table_row_right = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'border': 0,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })

        table_row_date = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 0,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy',
        })

        table_row_time = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 0,
            'font_name': 'Times New Roman',
            'num_format': 'hh:mm:ss',
        })

        table_row_datetime = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 0,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy hh:mm:ss',
        })

        outlet_names = []
        outlet_ids = []
        for x in report.outlet_ids:
            outlet_names.append(x.name)
            outlet_ids.append(x.id)

        if not outlet_names:
            outlet_names.append("ALL")

        if not outlet_ids:
            outlet_ids = self.env['br_multi_outlet.outlet'].search([]).ids

        # Now breakdown the ids in chunk of 40
        outlet_ids_list = list(chunks(outlet_ids, 40))

        ws.set_column(0, 65, 30, table_row_left)
        # ws.set_row(0, None, no_border)
        # ws.set_row(1, None, no_border)
        # ws.set_row(2, None, no_border)
        # ws.set_row(3, None, no_border)
        # ws.set_row(4, None, no_border)
        # REPORT'S HEADER
        ws.write('A1', u'Start Date', bold)
        ws.write_datetime('B1', datetime.strptime(report.start_date, "%Y-%m-%d"), table_row_date)
        ws.write('A2', u'End Date', bold)
        ws.write_datetime('B2', datetime.strptime(report.end_date, "%Y-%m-%d"), table_row_date)
        ws.write('A3', u'Outlet(s)', bold)
        ws.write('B3', ', '.join(outlet_names))
        ws.write('A5', u'Report Type', bold)
        if report.report_type:
            ws.write('B5', REPORTTYPE.get(report.report_type, ''))
        ws.write('A6', u'Transaction Type', bold)
        

        transaction_type = 'all'
        if report.trans_type: 
            transaction_type = report.trans_type

        if report.report_type == 'outlet_day':
            transaction_type = 'sale'
        
        ws.write('B6', TRANSTYPE.get(transaction_type))



        if report.report_type == 'tranc':



            # ------------------- Header -------------------
            ws.write('A10', 'Outlet', table_header)
            ws.write('B10', 'Outlet Code', table_header)
            ws.write('C10', 'Analytic Account', table_header)
            ws.write('D10', 'Area', table_header)
            ws.write('E10', 'Parent Area', table_header)
            ws.write('F10', 'Region', table_header)
            ws.write('G10', 'Asset Type', table_header)
            ws.write('H10', 'Location Type', table_header)
            ws.write('I10', 'Outlet Type', table_header)
            ws.write('J10', 'Outlet Status', table_header)
            ws.write('K10', 'Regional Manager', table_header)
            ws.write('L10', 'Area Manager', table_header)
            ws.write('M10', 'Sales Person', table_header)
            ws.write('N10', 'Session', table_header)
            ws.write('O10', 'Session Start Date', table_header)
            ws.write('P10', 'Session Close Date', table_header)
            ws.write('Q10', 'PIC1', table_header)
            ws.write('R10', 'PIC2', table_header)
            ws.write('S10', 'PIC3', table_header)
            ws.write('T10', 'Customer', table_header)
            ws.write('U10', 'Order Date', table_header)
            ws.write('V10', 'Order Time', table_header)
            ws.write('W10', 'Order Ref', table_header)
            ws.write('X10', 'Invoice Number', table_header)
            ws.write('Y10', '3rd Party ID', table_header)
            ws.write('Z10', 'Staff Redeem', table_header)
            ws.write('AA10','Remark', table_header)
            ws.write('AB10', 'Non-Sale', table_header)
            ws.write('AC10', 'Promotions', table_header)
            ws.write('AD10', 'Discount Name', table_header)
            ws.write('AE10', 'Discount Category 1', table_header)
            ws.write('AF10', 'Discount Category 2', table_header)
            ws.write('AG10', 'Discount Category 3', table_header)
            ws.write('AH10', 'Is Cancel Receipt', table_header)
            ws.write('AI10', 'Payment Amount', table_header)
            ws.write('AJ10', 'Total Before Discount (Excl Tax)', table_header)
            ws.write('AK10', 'Discount (Excl Tax)', table_header)

            #ws.write('Z10', 'Retail Sale - Price rounding', table_header)
            #ws.write('AA10', 'Retail Sale - Bill Rounding', table_header)
            #ws.write('AB10', 'Total after rounding', table_header)
            ws.write('AL10', 'Total After Discount (Excl Tax)', table_header)
            ws.write('AM10', 'Tax Before Discount', table_header)
            ws.write('AN10', 'Tax On Discount', table_header)
            ws.write('AO10', 'Tax Adjustment', table_header)
            ws.write('AP10', 'Tax After Discount', table_header)
            ws.write('AQ10', 'Total Before Payment Rounding', table_header)
            ws.write('AR10', 'Payment Rounding', table_header)
            ws.write('AS10', 'Total After Payment Rounding', table_header)
            ws.write('AT10', 'Net Sales After Payment Rounding', table_header)
            ws.write('AU10', 'On site Sales', table_header)
            ws.write('AV10', 'Off site Sales', table_header)
            ws.write('AW10', 'Redemption Sales', table_header)
            ws.write('AX10', 'Sale Date', table_header)
            ws.write('AY10', 'User', table_header)
            #ws.write('AW10', 'Comment', table_header)
            #ws.write('AJ10', 'Rounding', table_header)
            
            # Find the payment methods name
            payment_methods = [] # To store the payment method column number
            last_column = 51 # Indicate the last column from which we need to start
            for pm in self.env['account.journal'].search([('journal_user','=', 1),('is_rounding_method','=',False)]):
                last_column += 1
                columnname = colToExcel(last_column)
                payment_methods.append((pm.name, columnname))
                ws.write('%s10' % columnname, pm.name, table_header)

            # Calculate the date based on the user TZ, other wise report will display different then user see using filter
            user_id_report = report.user_id.id
            start_date = report.start_date + ' 05:00:01'
            start_date = fields.Datetime.from_string(start_date)
            start_date = start_date.strftime(DATE_FORMAT)
            utc_start_date = self.convert_timezone(self.env.user.tz, 'UTC', start_date)

            end_date = report.end_date + ' 05:00:00'
            end_date = datetime.strptime(end_date, DATE_FORMAT) + timedelta(days=1)
            end_date = end_date.strftime(DATE_FORMAT)
            utc_end_date = self.convert_timezone(self.env.user.tz, 'UTC', end_date)

            rounding_product_id = 0 
            if self.env.user.company_id and self.env.user.company_id.rounding_product_id:
                rounding_product_id = self.env.user.company_id.rounding_product_id.id

            next_row = 11 # After header this is the next row number 

            record_found = False

            for outletids in outlet_ids_list:

                sql_oulet_string = '1=1'
                if outletids:
                    sql_oulet_string = 'po.outlet_id in ' + str(outletids).replace('[', '(').replace(']', ')')

                credentials = {
                    'user_id_report': user_id_report,
                    'sql_oulet_string': sql_oulet_string,
                    'start_date': utc_start_date,
                    'end_date': utc_end_date,
                    'orderby': 'bmoo.name, ps.start_at, po.pos_reference',
                    'rounding_product_id' : rounding_product_id
                }

                report_data = self.get_report_data(credentials)


                prev_order = ''
                prev_AH = 0.0
                prev_AI = 0.0
                prev_AJ = 0.0
                prev_AK = 0.0
                prev_AL = 0.0
                prev_AM = 0.0
                prev_AN = 0.0
                prev_AO = 0.0
                prev_AP = 0.0
                prev_AQ = 0.0
                prev_AR = 0.0
                prev_AS = 0.0
                prev_AT = 0.0
                prev_AU = 0.0
                prev_AV = 0.0
                for line in report_data:

                    # Check if order have non-sale true and type is sale then ingnore this order
                    if line[27]:
                        if report.trans_type == 'sale':
                            continue
                    else:
                        if report.trans_type == 'nonsale':
                            continue

                    record_found = True

                    # Here we do row -1 because in this case this line is of the same order of previous line
                    if prev_order == line[18]:
                        next_row -= 1

                    ws.write('A%s' % next_row, line[0], table_row_left)
                    ws.write('B%s' % next_row, line[1], table_row_left)
                    ws.write('C%s' % next_row, line[38], table_row_left)
                    ws.write('D%s' % next_row, line[39], table_row_left)
                    ws.write('E%s' % next_row, line[40], table_row_left)
                    ws.write('F%s' % next_row, line[3], table_row_left)
                    ws.write('G%s' % next_row, line[4], table_row_left)
                    ws.write('H%s' % next_row, line[5], table_row_left)
                    ws.write('I%s' % next_row, line[6], table_row_left)
                    ws.write('J%s' % next_row, line[7], table_row_left)
                    ws.write('K%s' % next_row, line[8], table_row_left)
                    ws.write('L%s' % next_row, line[9], table_row_left)
                    ws.write('M%s' % next_row, line[14], table_row_left)
                    ws.write('N%s' % next_row, line[10], table_row_left)

                    start_at = self.convert_timezone('UTC', self.env.user.tz, line[11])
                    ws.write_datetime('O%s' % next_row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)

                    if line[12]:
                        stop_at = self.convert_timezone('UTC', self.env.user.tz, line[12])
                        ws.write_datetime('P%s' % next_row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                    else:
                        ws.write('P%s' % next_row, "", table_row_left)

                    ws.write('Q%s' % next_row, line[42], table_row_left)
                    ws.write('R%s' % next_row, line[43], table_row_left)
                    ws.write('S%s' % next_row, line[44], table_row_left)
                    ws.write('T%s' % next_row, line[41], table_row_left)

                    date_order = self.convert_timezone('UTC', self.env.user.tz,
                                                   '%s %s' % (line[15], line[16]))

                    ws.write_datetime('U%s' % next_row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
                    ws.write_datetime('V%s' % next_row, datetime.strptime(date_order.split(" ")[1], "%H:%M:%S"), table_row_time)

                    # print "ORDER======>>>>>", line['order_ref']
                    ws.write('W%s' % next_row, line[18], table_row_left)
                    ws.write('X%s' % next_row, line[19], table_row_left)
                    ws.write('Y%s' % next_row, line[47], table_row_left)
                    ws.write('Z%s' % next_row, line[45], table_row_left)
                    ws.write('AA%s' % next_row, line[30], table_row_left)
                    ws.write('AB%s' % next_row, line[27], table_row_left)
                    ws.write('AC%s' % next_row, line[46], table_row_left)

                    promotion_row = False
                    if line[21]:
                        promotions = line[21].split("|")
                        for p in promotions:
                            if not promotion_row:
                                p_data = p.split('###')
                                p_name = p_data[0]
                                p_categ = p_data[1].split("/")
                                p_voucher_code = p_data[2]
                                promotion_categ_len = len(p_categ)
                                if p_name:
                                    ws.write('AD%s' % next_row, p_name, table_row_left)
                                    ws.write('AE%s' % next_row, p_categ[0] if promotion_categ_len > 0 else "",
                                             table_row_left)
                                    ws.write('AF%s' % next_row, p_categ[1] if promotion_categ_len > 1 else "",
                                             table_row_left)
                                    ws.write('AG%s' % next_row, p_categ[2] if promotion_categ_len > 2 else "",
                                             table_row_left)
                                    promotion_row = True

                    if line[31] or line[32]:
                        ws.write_boolean('AH%s' % next_row, True, table_row_left)
                    else:
                        ws.write_boolean('AH%s' % next_row, False, table_row_left)
                    product_lines_total_with_tax = line[36] or 0.0

                    price_rounding = line[26] or 0.0
                    discount_lines_total_with_tax = line[37] or 0.0
                    entier_order_tax = (line[24] or 0.0) - (line[25] or 0.0)

                    # NOTE bellow logic is to make second line tax adjustment zero and use this for all calculation
                    # reason tax adjustment will be same for each split line
                    if prev_order != line[18]:
                        tax_adjustment = line[33]
                    else:
                        tax_adjustment = 0.0

                    total_after_discount_new = (product_lines_total_with_tax + price_rounding) - (
                        discount_lines_total_with_tax) - (entier_order_tax + tax_adjustment)
                    total_before_discount_new = total_after_discount_new - ( -1 * (line[22] or 0) )


                    if prev_order != line[18]:
                        ws.write('AJ%s' % next_row, total_before_discount_new, table_row_right)
                        prev_AJ = total_before_discount_new
                    else:
                        ws.write('AJ%s' % next_row, total_before_discount_new + prev_AJ, table_row_right)

                    if prev_order != line[18]:
                        ws.write('AK%s' % next_row, -1 * (line[22] or 0), table_row_right)
                        prev_AK = -1 * (line[22] or 0)
                    else:
                        ws.write('AK%s' % next_row, (-1 * (line[22] or 0) ) + prev_AK, table_row_right)

                    total_after_discount = (line[23] or 0.0) - (line[22] or 0.0)


                    if prev_order != line[18]:
                        ws.write('AL%s' % next_row, total_after_discount_new, table_row_right)
                        prev_AL = total_after_discount_new
                    else:
                        ws.write('AL%s' % next_row, total_after_discount_new + prev_AL, table_row_right)
                    # print "=----DFSDF====>>>>", (line['tax'] or 0.0) , line['tax_adjustment'], line['order_ref']
                    # print "=----DFSDF====>>>>", (line['tax'] or 0.0) + line['tax_adjustment'], line['order_ref']

                    #ws.write('Z%s' % next_row, line[26], table_row_right)


                    #ws.write('AA%s' % next_row, line[35] or 0.0 * -1 , table_row_right)
                    total_after_rounding = total_after_discount_new + line[26] + ( (line[35] or 0.0) * -1 )
                    #ws.write('AB%s' % next_row, total_after_rounding , table_row_right)


                    gst_before_discount = (line[24] or 0.0) #+ (tax_adjustment or 0.0)
                    if prev_order != line[18]:
                        ws.write('AM%s' % next_row, gst_before_discount, table_row_right)
                        prev_AM = gst_before_discount
                    else:
                        ws.write('AM%s' % next_row, gst_before_discount + prev_AM, table_row_right)

                    if prev_order != line[18]:
                        ws.write('AN%s' % next_row, (line[25] or 0.0) * -1 , table_row_right)
                        prev_AN = (line[25] or 0.0) * -1
                    else:
                        ws.write('AN%s' % next_row, ( (line[25] or 0.0) * -1 ) + prev_AN, table_row_right)

                    # AN Tax adjustment we already handle manually to make zero for second line
                    if prev_order != line[18]:
                        ws.write('AO%s' % next_row, tax_adjustment or 0.0, table_row_right)
                        prev_AO = tax_adjustment or 0.0
                    else:
                        ws.write('AO%s' % next_row, (tax_adjustment or 0.0) + prev_AO, table_row_right)

                    gst_after_discount = gst_before_discount - (line[25] or 0.0) + (tax_adjustment or 0.0)

                    if prev_order != line[18]:
                        ws.write('AP%s' % next_row, gst_after_discount , table_row_right)
                        prev_AP = gst_after_discount
                    else:
                        ws.write('AP%s' % next_row, gst_after_discount + prev_AP, table_row_right)

                    total_before_payment_rounding = total_after_discount_new + gst_after_discount

                    if prev_order != line[18]:
                        ws.write('AQ%s' % next_row, total_before_payment_rounding, table_row_right)
                        prev_AQ = total_before_payment_rounding
                    else:
                        ws.write('AQ%s' % next_row, total_before_payment_rounding + prev_AQ, table_row_right)

                    # NOTE bellow logic is to make second line payment rounding zero and use this for all calculation
                    # reason payment rounding will be same for each split line
                    if prev_order != line[18]:
                        payment_rounding = (line[35] or 0.0) * -1
                    else:
                        payment_rounding = 0.0

                    # AN Tax adjustment we already handle manually to make zero for second line
                    if prev_order != line[18]:
                        ws.write('AR%s' % next_row, payment_rounding, table_row_right)
                        prev_AR = payment_rounding
                    else:
                        ws.write('AR%s' % next_row, payment_rounding + prev_AR , table_row_right)
                    total_sale = total_before_payment_rounding + payment_rounding
                    # previous calc of net total as below
                    # total_after_discount - (line[34] and gst_after_discount or 0)

                    if prev_order != line[18]:
                        ws.write('AS%s' % next_row, total_sale , table_row_right)
                        prev_AS = total_sale
                    else:
                        ws.write('AS%s' % next_row, total_sale + prev_AS, table_row_right)


                    # NOTE: Bellow logic is for tax need to make opposite sign when there is tax is nagative in normal order
                    # same way if in refund order tax is positive then need to make opposite sign and do calculation
                    if not line[31]:
                        if gst_after_discount < 0:
                            net_sale_after_payment_rounding = total_sale - (gst_after_discount * -1)
                        else:
                            net_sale_after_payment_rounding = total_sale - gst_after_discount
                    else:
                        if gst_after_discount > 0:
                            net_sale_after_payment_rounding = total_sale - (gst_after_discount * -1)
                        else:
                            net_sale_after_payment_rounding = total_sale - gst_after_discount


                    if prev_order != line[18]:
                        ws.write('AT%s' % next_row, net_sale_after_payment_rounding, table_row_right)
                        prev_AT = net_sale_after_payment_rounding
                    else:
                        ws.write('AT%s' % next_row, net_sale_after_payment_rounding + prev_AT, table_row_right)


                    # ws.write('AC%s' % next_row, total_after_discount - gst_after_discount, table_row_right)

                    # this below AG AH AI cell fill from payment detail loop, check below.
                    # ws.write('AG%s' % next_row, , table_row_right)
                    # ws.write('AH%s' % next_row, , table_row_right)
                    # ws.write('AI%s' % next_row, , table_row_right)

                    sale_date = self.convert_timezone('UTC', self.env.user.tz, '%s %s' % (line[15], line[16]))
                    sale_date_to_check = fields.Datetime.from_string(sale_date)
                    twelve_up_time = sale_date.split(" ")[0] + ' 00:00:01'
                    upto_five_time = sale_date.split(" ")[0] + ' 05:00:00'
                    sale_date = datetime.strptime(sale_date, '%Y-%m-%d %H:%M:%S')
                    if (sale_date_to_check >= fields.Datetime.from_string(twelve_up_time)) and (sale_date_to_check <= fields.Datetime.from_string(upto_five_time)):
                        ws.write_datetime('AX%s' % next_row, sale_date.replace(hour=0, minute=0, second=0) - timedelta(days=1), table_row_date)
                    else:
                        ws.write_datetime('AX%s' % next_row, sale_date.replace(hour=0, minute=0, second=0), table_row_date)

                    ws.write('AY%s' % next_row, line[13], table_row_left)
                    #ws.write('AW%s' % next_row, line[30], table_row_left)
                    ##ws.write('AJ%s' % next_row, line[26] or 0.0, table_row_right)


                    pos_order_amount_total = 0.0
                    total_payment_on_site_type = 0.0
                    total_payment_off_site_type = 0.0
                    total_payment_redemption_type = 0.0
                    total_all_type = 0.0
                    if line[28]:
                        payments = line[28].split("|")
                        for pm in payments:
                            pm_data = pm.split(",")
                            if len(pm_data) > 1 :
                                pm_amount = float(pm_data[1]) if pm_data[1].strip() else pm_data[1]
                                if pm_amount != " " and pm_data[3] != 'is_rounding_method':
                                    total_all_type += float(pm_amount)
                                    if pm_data[2] == 'on_site':
                                        total_payment_on_site_type += float(pm_amount)
                                    elif pm_data[2] == 'off_site':
                                        total_payment_off_site_type += float(pm_amount)
                                    else:
                                        total_payment_redemption_type += float(pm_amount)
                                    on_site = round(total_payment_on_site_type  ,2)
                                    off_site = round(total_payment_off_site_type  ,2)
                                    redumption = round(total_payment_redemption_type ,2)

                                    ws.write('AU%s' % next_row, on_site , table_row_right)
                                    ws.write('AV%s' % next_row, off_site , table_row_right)
                                    ws.write('AW%s' % next_row, redumption ,table_row_right)

                                    match_payment_method = False
                                    method_name = pm_data[0]
                                    for payment_method in payment_methods:
                                        if payment_method[0] == method_name:
                                            match_payment_method = payment_method[1]
                                            break
                                    if pm_data[3] != 'is_rounding_method':
                                        pos_order_amount_total += float(pm_amount)
                                        if match_payment_method:
                                            ws.write('%s%s' % (match_payment_method, next_row), pm_amount, table_row_right)
                                        else:
                                            last_column += 1
                                            columnname = colToExcel(last_column)
                                            payment_methods.append((method_name, columnname))
                                            ws.write('%s10' % columnname, method_name, table_header)
                                            ws.write('%s%s' % (columnname, next_row), pm_amount, table_row_right)

                    # NOTE : this condition to print sum of order only on one line
                    # (because order will split if there is not tax in any line or different
                    #  kind of tax like one in inclusive and another exclusive)

                    # AH:payment amount no need to check the split line logic
                    ws.write('AI%s' % next_row, pos_order_amount_total, table_row_right)

                    next_row += 1
                    prev_order = line[18]

            if record_found:
                ws.write('AG%s' % next_row, "Total", table_header)

                next_row_str = str(next_row-1)
                ws.write_formula('AH%s' % next_row, "{=SUM(AH11:AH%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AI%s' % next_row, "{=SUM(AI11:AI%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AJ%s' % next_row, "{=SUM(AJ11:AJ%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AK%s' % next_row, "{=SUM(AK11:AK%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AL%s' % next_row, "{=SUM(AL11:AL%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AM%s' % next_row, "{=SUM(AM11:AM%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AN%s' % next_row, "{=SUM(AN11:AN%s)}" % next_row_str, table_row_right_1)

                ws.write_formula('AO%s' % next_row, "{=SUM(AO11:AO%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AP%s' % next_row, "{=SUM(AP11:AP%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AQ%s' % next_row, "{=SUM(AQ11:AQ%s)}" % next_row_str, table_row_right_1)

                ws.write_formula('AR%s' % next_row, "{=SUM(AR11:AR%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AS%s' % next_row, "{=SUM(AS11:AS%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AT%s' % next_row, "{=SUM(AT11:AT%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AU%s' % next_row, "{=SUM(AU11:AU%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AV%s' % next_row, "{=SUM(AV11:AV%s)}" % next_row_str, table_row_right_1)
                ws.write_formula('AW%s' % next_row, "{=SUM(AW11:AW%s)}" % next_row_str, table_row_right_1)



                for colnum in range(52, last_column+1):
                    columnname = colToExcel(colnum)
                    ws.write_formula('%s%s' % (columnname, next_row), "{=SUM(%s11:%s%s)}" % (columnname, columnname, next_row_str), table_row_right_1)


        else:

            # ------------------- Header -------------------
            ws.write('A10', 'Outlet', table_header)
            ws.write('B10', 'Outlet Code', table_header)
            ws.write('C10', 'Region', table_header)
            ws.write('D10', 'Outlet Type', table_header)
            ws.write('E10', 'Outlet Status', table_header)
            ws.write('F10', 'Regional Manager', table_header)
            ws.write('G10', 'Area Manager', table_header)
            ws.write('H10', 'Session Start Date', table_header)
            ws.write('I10', 'Session Close Date', table_header)
            ws.write('J10', 'Order Date', table_header)
            ws.write('K10', 'Payment Amount', table_header)
            ws.write('L10', 'Total Before Discount (Excl Tax)', table_header)
            ws.write('M10', 'Discount (Excl Tax)', table_header)
            ws.write('N10', 'Total After Discount (Excl Tax)', table_header)

            # ws.write('O10', 'Retail Sale - Price rounding', table_header)
            # ws.write('P10', 'Retail Sale - Bill Rounding', table_header)
            # ws.write('Q10', 'Total after rounding', table_header)


            ws.write('O10', 'Tax Before Discount', table_header)
            ws.write('P10', 'Tax On Discount', table_header)
            ws.write('Q10', 'Tax Adjustment', table_header)
            ws.write('R10', 'Tax After Discount', table_header)
            ws.write('S10', 'Total Before Payment Rounding', table_header)
            ws.write('T10', 'Payment Rounding', table_header)
            ws.write('U10', 'Total After Payment Rounding', table_header)
            ws.write('V10', 'Net Sales After Payment Rounding', table_header)

            ws.write('W10', 'On site Sales', table_header)
            ws.write('X10', 'Off site Sales', table_header)
            ws.write('Y10', 'Redemption Sales', table_header)

            ws.write('Z10', 'Sale Date', table_header)

            ws.write('AA10', 'All TC', table_header)
            ws.write('AB10', 'All TC Average', table_header)
            ws.write('AC10', 'Z-report TC', table_header)

            payment_methods = [] # To store the payment method column number
            last_column = 29 # Indicate the last column from which we need to start
            for pm in self.env['account.journal'].search([('journal_user','=', 1),('is_rounding_method','=',False)]):
                last_column += 1
                columnname = colToExcel(last_column)
                payment_methods.append((pm.name, columnname))
                ws.write('%s10' % columnname, pm.name, table_header)



            user_id_report = report.user_id.id
            start_date = report.start_date + ' 05:00:01'
            start_date = fields.Datetime.from_string(start_date)
            start_date = start_date.strftime(DATE_FORMAT)
            utc_start_date = self.convert_timezone(self.env.user.tz, 'UTC', start_date)

            end_date = report.end_date + ' 05:00:00'
            end_date = datetime.strptime(end_date, DATE_FORMAT) + timedelta(days=1)
            end_date = end_date.strftime(DATE_FORMAT)
            utc_end_date = self.convert_timezone(self.env.user.tz, 'UTC', end_date)

            rounding_product_id = 0 
            if self.env.user.company_id and self.env.user.company_id.rounding_product_id:
                rounding_product_id = self.env.user.company_id.rounding_product_id.id

            next_row = 10
            # payment_methods = []
            LinePosMethods = {}
            # last_column = 22
            last_outlet_id = 0
            last_outlet_date = "1800-10-01"
            last_line_number = 11

            PosBeforeAmount = 0.0
            PosDiscount = 0.0
            PosDiscountNegative = 0.0
            PosAfterDiscount = 0.0
            product_lines_total_with_tax = 0.0
            price_rounding = 0.0
            discount_lines_total_with_tax = 0.0
            entier_order_tax = 0.0
            tax_adjustment = 0.0
            PosAfterDiscountNew = 0.0
            total_before_discount_new = 0.0
            PosGstBeforeDiscount = 0.0
            PosGstAfterDiscount = 0.0
            net_calc_PosGstAfterDiscount = 0.0
            PosGstOnDiscount = 0.0
            PosNetTotal = 0.0
            PosRounding = 0.0
            PosPaymentRounding = 0.0
            PosTotalPay = 0.0
            prev_order = ''

            needtoaddline = False
            ticket_count = 0
            without_payment_count = 0
            record_found = False

            for outletids in outlet_ids_list:
                sql_oulet_string = '1=1'
                if outletids:
                    sql_oulet_string = 'po.outlet_id in ' + str(outletids).replace('[', '(').replace(']', ')')

                credentials = {
                    'user_id_report': user_id_report,
                    'sql_oulet_string': sql_oulet_string,
                    'start_date': utc_start_date,
                    'end_date': utc_end_date,
                    'orderby': 'bmoo.name, po.date_order, ps.start_at, po.pos_reference',
                    'rounding_product_id': rounding_product_id
                }

                report_data = self.get_report_data(credentials)


                for line in report_data:
                    if line[27]:
                        continue
                    record_found = True
                     # = self.convert_timezone('UTC', self.env.user.tz, line['order_date'])

                    date_order_user = self.convert_timezone('UTC', self.env.user.tz, '%s %s' % (line[15], line[16]))

                    if last_outlet_id != int(line[2]):
                        
                        last_outlet_id = int(line[2])
                        last_outlet_date = "1800-10-01"
                        ticket_count = 0
                        without_payment_count = 0

                        PosBeforeAmount = 0.0
                        PosDiscount = 0.0
                        PosDiscountNegative = 0.0
                        PosAfterDiscount = 0.0
                        product_lines_total_with_tax = 0.0
                        price_rounding = 0.0
                        discount_lines_total_with_tax = 0.0
                        entier_order_tax = 0.0
                        tax_adjustment = 0.0
                        PosAfterDiscountNew = 0.0
                        total_before_discount_new = 0.0
                        PosGstBeforeDiscount = 0.0
                        PosGstAfterDiscount = 0.0
                        net_calc_PosGstAfterDiscount = 0.0
                        PosGstOnDiscount = 0.0
                        PosNetTotal = 0.0
                        PosRounding = 0.0
                        PosPaymentRounding = 0.0
                        PosTotalPay = 0.0

                        LinePosMethods = {}

                        if next_row != 10:
                            next_row += 1
                            # Need to add the total line
                            ws.write('J%s' % next_row, "Total", table_header)

                            next_row_str = str(next_row-1)
                            last_line_number_str = str(last_line_number)
                            ws.write_formula('K%s' % next_row, "{=SUM(K%s:K%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('L%s' % next_row, "{=SUM(L%s:L%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('M%s' % next_row, "{=SUM(M%s:M%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('N%s' % next_row, "{=SUM(N%s:N%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('O%s' % next_row, "{=SUM(O%s:O%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('P%s' % next_row, "{=SUM(P%s:P%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('Q%s' % next_row, "{=SUM(Q%s:Q%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('R%s' % next_row, "{=SUM(R%s:R%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('S%s' % next_row, "{=SUM(S%s:S%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('T%s' % next_row, "{=SUM(T%s:T%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('U%s' % next_row, "{=SUM(U%s:U%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('V%s' % next_row, "{=SUM(V%s:V%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('W%s' % next_row, "{=SUM(W%s:W%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('X%s' % next_row, "{=SUM(X%s:X%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('Y%s' % next_row, "{=SUM(Y%s:Y%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('AA%s' % next_row, "{=SUM(AA%s:AA%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('AB%s' % next_row, "{=SUM(AB%s:AB%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            ws.write_formula('AC%s' % next_row, "{=SUM(AC%s:AC%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                            
                            for colnum in range(26, last_column+1):
                                columnname = colToExcel(colnum)
                                ws.write_formula('%s%s' % (columnname, next_row), "{=SUM(%s%s:%s%s)}" % (columnname,last_line_number_str, columnname, next_row_str), table_row_right)
                            last_line_number = next_row+1
                    flag_last_date = False
                    need_to_merge = True
                    if (fields.Date.from_string(date_order_user.split(" ")[0]) != fields.Date.from_string(last_outlet_date.split(" ")[0])):
                        need_to_add = False
                        sale_date_to_check = fields.Datetime.from_string(date_order_user)
                        twelve_up_time = date_order_user.split(" ")[0] + ' 00:00:01'
                        upto_five_time = date_order_user.split(" ")[0] + ' 05:00:00'
                        if (sale_date_to_check >= fields.Datetime.from_string(twelve_up_time)) and (sale_date_to_check <= fields.Datetime.from_string(upto_five_time)):
                            sale_date_only = datetime.strptime(date_order_user.split(" ")[0], "%Y-%m-%d") - timedelta(days=1)
                            sale_date_only_str = sale_date_only.strftime(DATE_FORMAT)
                            if fields.Date.from_string(last_outlet_date.split(" ")[0]) != fields.Date.from_string(sale_date_only_str.split(" ")[0]):
                                need_to_add = True
                                flag_last_date = True
                        else:
                            need_to_add = True

                        if need_to_add:
                            need_to_merge = False
                            next_row += 1
                            if line[31] or line[32]:
                                ticket_count = 0
                            else:
                                ticket_count = 1
                            last_outlet_date = date_order_user
                            ws.write('A%s' % next_row, line[0], table_row_left)
                            ws.write('B%s' % next_row, line[1], table_row_left)
                            ws.write('C%s' % next_row, line[3], table_row_left)
                            ws.write('D%s' % next_row, line[6], table_row_left)
                            ws.write('E%s' % next_row, line[7], table_row_left)
                            ws.write('F%s' % next_row, line[8], table_row_left)
                            ws.write('G%s' % next_row, line[9], table_row_left)

                            start_at = self.convert_timezone('UTC', self.env.user.tz, line[11])
                            ws.write_datetime('H%s' % next_row, datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                            
                            
                            if line[12]:
                                stop_at = self.convert_timezone('UTC', self.env.user.tz, line[12])
                                ws.write_datetime('I%s' % next_row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)
                            else:
                                ws.write('I%s' % next_row, "", table_row_left)

                            date_order = self.convert_timezone('UTC', self.env.user.tz,
                                                       '%s %s' % (line[15], line[16]))

                            if flag_last_date:
                                ws.write_datetime('J%s' % next_row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d") - timedelta(days=1), table_row_date)
                            else:
                                ws.write_datetime('J%s' % next_row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)
                            
                            PosBeforeAmount = 0.0
                            PosDiscount = 0.0
                            PosDiscountNegative = 0.0
                            PosAfterDiscount = 0.0
                            product_lines_total_with_tax = 0.0
                            price_rounding = 0.0
                            discount_lines_total_with_tax = 0.0
                            entier_order_tax = 0.0
                            tax_adjustment = 0.0
                            PosAfterDiscountNew = 0.0
                            total_before_discount_new = 0.0
                            PosGstBeforeDiscount = 0.0
                            PosGstAfterDiscount = 0.0
                            net_calc_PosGstAfterDiscount = 0.0
                            PosGstOnDiscount = 0.0
                            PosNetTotal = 0.0
                            PosRounding = 0.0
                            PosPaymentRounding = 0.0
                            PosTotalPay = 0.0

                            LinePosMethods = {}
                            LinePosType = {'total': 0}
                            

                            PosBeforeAmount += (line[23] or 0.0)
                            PosDiscount += (line[22] or 0.0)
                            PosDiscountNegative += (-1 * (line[22] or 0))
                            total_after_discount = (line[23] or 0.0) - (line[22] or 0.0)
                            PosAfterDiscount = PosBeforeAmount - PosDiscount

                            product_lines_total_with_tax += line[36] or 0.0
                            price_rounding += line[26] or 0.0
                            discount_lines_total_with_tax += line[37] or 0.0
                            entier_order_tax += (line[24] or 0.0) - (line[25] or 0.0)
                            to_use_net_calc_adj = 0
                            if prev_order != line[18]:
                                tax_adjustment += line[33]
                                to_use_net_calc_adj = line[33]

                            PosAfterDiscountNew = (product_lines_total_with_tax + price_rounding) - (
                                discount_lines_total_with_tax) - (entier_order_tax + tax_adjustment)

                            PosGstBeforeDiscount += (line[24] or 0.0) #+ (line[33] or 0.0)
                            PosGstOnDiscount += (line[25] or 0.0)
                            PosGstAfterDiscount = PosGstBeforeDiscount + (-1 * PosGstOnDiscount) + tax_adjustment


                            to_use_in_net_calc_gst_after_discount = (line[24] or 0.0) + (-1 *  (line[25] or 0.0)) + to_use_net_calc_adj


                            if not line[31]:
                                if to_use_in_net_calc_gst_after_discount < 0:
                                    net_calc_PosGstAfterDiscount +=  to_use_in_net_calc_gst_after_discount * -1
                                else:
                                    net_calc_PosGstAfterDiscount += to_use_in_net_calc_gst_after_discount
                            else:
                                if to_use_in_net_calc_gst_after_discount > 0:
                                    net_calc_PosGstAfterDiscount += to_use_in_net_calc_gst_after_discount * -1
                                else:
                                    net_calc_PosGstAfterDiscount += to_use_in_net_calc_gst_after_discount

                            PosRounding += line[26] or 0.0
                            if prev_order != line[18]:
                                PosPaymentRounding += (line[35] or 0.0) * -1
                            # PosNetTotal = PosAfterDiscount - PosGstAfterDiscount
                            # PosNetTotal = PosAfterDiscount - (line[34] and PosGstAfterDiscount or 0)

                            PosNetTotal = PosAfterDiscountNew + PosGstAfterDiscount + PosPaymentRounding

                            ws.write('L%s' % next_row, PosAfterDiscountNew - PosDiscountNegative, table_row_right)
                            ws.write('M%s' % next_row, -1 * (PosDiscount), table_row_right)
                            ws.write('N%s' % next_row, PosAfterDiscountNew, table_row_right)

                            # ws.write('O%s' % next_row, PosRounding, table_row_right)
                            # ws.write('P%s' % next_row, PosPaymentRounding, table_row_right)
                            # ws.write('Q%s' % next_row, PosAfterDiscount + PosRounding + PosPaymentRounding , table_row_right)

                            ws.write('O%s' % next_row, PosGstBeforeDiscount, table_row_right)
                            ws.write('P%s' % next_row, -1 * (PosGstOnDiscount), table_row_right)
                            ws.write('Q%s' % next_row, tax_adjustment, table_row_right)
                            ws.write('R%s' % next_row, PosGstAfterDiscount, table_row_right)
                            ws.write('S%s' % next_row, PosAfterDiscountNew + PosGstAfterDiscount, table_row_right)
                            ws.write('T%s' % next_row, PosPaymentRounding, table_row_right)
                            ws.write('U%s' % next_row, PosNetTotal, table_row_right)

                            ws.write('V%s' % next_row, PosNetTotal - net_calc_PosGstAfterDiscount, table_row_right)

                            # below V W X is in payment part
                            # ws.write('V%s' % next_row, "bring value", table_row_right)
                            # ws.write('W%s' % next_row, "bring value", table_row_right)
                            # ws.write('X%s' % next_row, "bring value", table_row_right)

                            if flag_last_date:
                                ws.write_datetime('Z%s' % next_row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d") - timedelta(days=1), table_row_date)
                            else:
                                ws.write_datetime('Z%s' % next_row, datetime.strptime(date_order.split(" ")[0], "%Y-%m-%d"), table_row_date)


                            ws.write('AA%s' % next_row, ticket_count, table_row_right)
                            if ticket_count:
                                ws.write('AB%s' % next_row, PosNetTotal/ticket_count, table_row_right)
                            else:
                                ws.write('AB%s' % next_row, 0.0, table_row_right)
                            

                            pos_order_amount_total = 0.0

                            if line[28]:

                                payments = line[28].split("|")
                                if payments and len(payments) == 1:
                                    first_amount_line = payments[0].split(",")
                                    if not first_amount_line[1].strip():
                                        without_payment_count = 1

                                ws.write('AC%s' % next_row, ticket_count - without_payment_count, table_row_right)

                                for pm in payments:
                                    pm_data = pm.split(",")
                                    if len(pm_data) > 1 :
                                        pm_amount = float(pm_data[1]) if pm_data[1].strip() else pm_data[1]
                                        if pm_amount != " " and pm_data[3] != 'is_rounding_method':
                                            if prev_order != line[18]:  # this condidion is if not same order as previous
                                            
                                                LinePosType['total'] += float(pm_amount)
                                                type_name = pm_data[2]
                                                if LinePosType.get(type_name, False):
                                                    LinePosType[type_name] = (LinePosType.get(type_name) + float(pm_amount))
                                                else:
                                                    LinePosType[type_name] = float(pm_amount)

                                                if 'on_site' in LinePosType:
                                                    ws.write('W%s' % next_row,
                                                             round(LinePosType['on_site'], 2),
                                                             table_row_right)
                                                else:
                                                    ws.write('W%s' % next_row, 0, table_row_right)
                                                if 'off_site' in LinePosType:
                                                    ws.write('X%s' % next_row,
                                                             round(LinePosType['off_site'], 2),
                                                             table_row_right)
                                                else:
                                                    ws.write('X%s' % next_row, 0, table_row_right)
                                                if 'redemption' in LinePosType:
                                                    ws.write('Y%s' % next_row,
                                                             round(LinePosType['redemption'], 2),
                                                             table_row_right)
                                                else:
                                                    ws.write('Y%s' % next_row, 0, table_row_right)



                                                method_name = pm_data[0]
                                                if LinePosMethods.get(method_name, False):
                                                    LinePosMethods[method_name] = (LinePosMethods.get(method_name)+ float(pm_amount))
                                                else:
                                                    LinePosMethods[method_name] = float(pm_amount)

                                                match_payment_method = False

                                                for payment_method in payment_methods:
                                                    if payment_method[0] == method_name:
                                                        match_payment_method = payment_method[1]
                                                        break
                                                if pm_data[3] != 'is_rounding_method':
                                                    pos_order_amount_total += float(pm_amount)
                                                    if match_payment_method:
                                                        ws.write('%s%s' % (match_payment_method, next_row), LinePosMethods.get(method_name), table_row_right)
                                                    else:
                                                        last_column += 1
                                                        columnname = colToExcel(last_column)
                                                        payment_methods.append((method_name, columnname))
                                                        ws.write('%s10' % columnname, method_name, table_header)
                                                        ws.write('%s%s' % (columnname, next_row), LinePosMethods.get(method_name), table_row_right)



                            PosTotalPay += pos_order_amount_total
                            ws.write('K%s' % next_row, PosTotalPay, table_row_right)
                        

                    if need_to_merge:

                        if line[12]:
                            stop_at = self.convert_timezone('UTC', self.env.user.tz, line[12])
                            ws.write_datetime('I%s' % next_row, datetime.strptime(stop_at, "%Y-%m-%d %H:%M:%S"), table_row_datetime)

                        if line[31] or line[32]:
                            print "Nothing to do with it"
                        else:
                            if prev_order != line[18]: # this condidion is if not same order as previous
                                ticket_count += 1

                        PosBeforeAmount += line[23] or 0.0
                        PosDiscount += line[22] or 0.0
                        PosDiscountNegative += (-1 * (line[22] or 0))
                        total_after_discount = (line[23] or 0) - (line[22] or 0)
                        PosAfterDiscount = PosBeforeAmount - PosDiscount

                        product_lines_total_with_tax += line[36] or 0.0
                        price_rounding += line[26] or 0.0
                        discount_lines_total_with_tax += line[37] or 0.0
                        entier_order_tax += (line[24] or 0.0) - (line[25] or 0.0)
                        to_use_net_calc_adj = 0
                        if prev_order != line[18]:
                            tax_adjustment += line[33]
                            to_use_net_calc_adj = line[33]

                        PosAfterDiscountNew = (product_lines_total_with_tax + price_rounding) - (
                            discount_lines_total_with_tax) - (entier_order_tax + tax_adjustment)

                        PosGstBeforeDiscount += (line[24] or 0.0 ) #+ (line[33] or 0.0)
                        PosGstOnDiscount += (line[25] or 0.0)
                        PosGstAfterDiscount = PosGstBeforeDiscount + (-1 * PosGstOnDiscount) + tax_adjustment
                        to_use_in_net_calc_gst_after_discount = (line[24] or 0.0) + (
                                    -1 * (line[25] or 0.0)) + to_use_net_calc_adj

                        if not line[31]:
                            if to_use_in_net_calc_gst_after_discount < 0:
                                net_calc_PosGstAfterDiscount += to_use_in_net_calc_gst_after_discount * -1
                            else:
                                net_calc_PosGstAfterDiscount += to_use_in_net_calc_gst_after_discount
                        else:
                            if to_use_in_net_calc_gst_after_discount > 0:
                                net_calc_PosGstAfterDiscount += to_use_in_net_calc_gst_after_discount * -1
                            else:
                                net_calc_PosGstAfterDiscount += to_use_in_net_calc_gst_after_discount


                        PosRounding += line[26] or 0.0
                        if prev_order != line[18]:
                            PosPaymentRounding += (line[35] or 0.0) * -1

                        # PosNetTotal = PosAfterDiscount - (line[34] and PosGstAfterDiscount or 0)

                        PosNetTotal = PosAfterDiscountNew + PosGstAfterDiscount + PosPaymentRounding


                        
                        ws.write('L%s' % next_row, PosAfterDiscountNew - PosDiscountNegative, table_row_right)
                        ws.write('M%s' % next_row, -1 * (PosDiscount), table_row_right)
                        ws.write('N%s' % next_row, PosAfterDiscountNew, table_row_right)

                        # ws.write('O%s' % next_row, PosRounding, table_row_right)
                        # ws.write('P%s' % next_row, PosPaymentRounding, table_row_right)
                        # ws.write('Q%s' % next_row, PosAfterDiscount + PosRounding + PosPaymentRounding , table_row_right)

                        ws.write('O%s' % next_row, PosGstBeforeDiscount, table_row_right)
                        ws.write('P%s' % next_row, -1 * (PosGstOnDiscount), table_row_right)
                        ws.write('Q%s' % next_row, tax_adjustment, table_row_right)
                        ws.write('R%s' % next_row, PosGstAfterDiscount, table_row_right)
                        ws.write('S%s' % next_row, PosAfterDiscountNew + PosGstAfterDiscount, table_row_right)
                        ws.write('T%s' % next_row, PosPaymentRounding, table_row_right)
                        ws.write('U%s' % next_row, PosNetTotal, table_row_right)

                        ws.write('V%s' % next_row,PosNetTotal - net_calc_PosGstAfterDiscount, table_row_right)

                        # below v w x is in payment loop
                        # ws.write('V%s' % next_row, "bring value", table_row_right)
                        # ws.write('W%s' % next_row, "bring value", table_row_right)
                        # ws.write('X%s' % next_row, "bring value", table_row_right)

                        ws.write('AA%s' % next_row, ticket_count, table_row_right)
                        
                        if ticket_count:
                            ws.write('AB%s' % next_row, PosNetTotal/ticket_count, table_row_right)
                        else:
                            ws.write('AB%s' % next_row, 0.0, table_row_left)


                        # Now dynamic payment method logic goes here
                        pos_order_amount_total = 0.0

                        if line[28]:
                            payments = line[28].split("|")
                            if payments and len(payments) == 1:
                                first_amount_line = payments[0].split(",")
                                if not first_amount_line[1].strip():
                                    without_payment_count += 1


                            ws.write('AC%s' % next_row, ticket_count - without_payment_count , table_row_right)

                            for pm in payments:
                                pm_data = pm.split(",")
                                if len(pm_data) > 1 :
                                    pm_amount = float(pm_data[1]) if pm_data[1].strip() else pm_data[1]
                                    if pm_amount != " " and pm_data[3] != 'is_rounding_method':
                                        if prev_order != line[18]:  # this condidion is if not same order as previous

                                            LinePosType['total'] += float(pm_amount)
                                            type_name = pm_data[2]
                                            if LinePosType.get(type_name, False):
                                                LinePosType[type_name] = (LinePosType.get(type_name) + float(pm_amount))
                                            else:
                                                LinePosType[type_name] = float(pm_amount)

                                            if 'on_site' in LinePosType:
                                                ws.write('W%s' % next_row,
                                                         round(LinePosType['on_site'], 2),
                                                         table_row_right)
                                            else:
                                                ws.write('W%s' % next_row, 0, table_row_right)
                                            if 'off_site' in LinePosType:
                                                ws.write('X%s' % next_row,
                                                         round(LinePosType['off_site'], 2),
                                                         table_row_right)
                                            else:
                                                ws.write('X%s' % next_row, 0, table_row_right)
                                            if 'redemption' in LinePosType:
                                                ws.write('Y%s' % next_row,
                                                         round(LinePosType['redemption'], 2),
                                                         table_row_right)
                                            else:
                                                ws.write('Y%s' % next_row, 0, table_row_right)

                                            method_name = pm_data[0]
                                            if LinePosMethods.get(method_name, False):
                                                LinePosMethods[method_name] = (LinePosMethods.get(method_name)+ float(pm_amount))
                                            else:
                                                LinePosMethods[method_name] = float(pm_amount)

                                            match_payment_method = False

                                            for payment_method in payment_methods:
                                                if payment_method[0] == method_name:
                                                    match_payment_method = payment_method[1]
                                                    break
                                            if pm_data[3] != 'is_rounding_method':
                                                pos_order_amount_total += float(pm_amount)
                                                if match_payment_method:
                                                    ws.write('%s%s' % (match_payment_method, next_row), LinePosMethods.get(method_name), table_row_right)
                                                else:
                                                    last_column += 1
                                                    columnname = colToExcel(last_column)
                                                    payment_methods.append((method_name, columnname))
                                                    ws.write('%s10' % columnname, method_name, table_header)
                                                    ws.write('%s%s' % (columnname, next_row), LinePosMethods.get(method_name), table_row_right)

                        if prev_order != line[18]:
                            PosTotalPay += pos_order_amount_total
                        ws.write('K%s' % next_row, PosTotalPay, table_row_right)
                    prev_order = line[18]

            next_row += 1

            if record_found:
                ws.write('J%s' % next_row, "Total", table_header)

                next_row_str = str(next_row-1)
                last_line_number_str = str(last_line_number)
                ws.write_formula('K%s' % next_row, "{=SUM(K%s:K%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('L%s' % next_row, "{=SUM(L%s:L%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('M%s' % next_row, "{=SUM(M%s:M%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('N%s' % next_row, "{=SUM(N%s:N%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('O%s' % next_row, "{=SUM(O%s:O%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('P%s' % next_row, "{=SUM(P%s:P%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('Q%s' % next_row, "{=SUM(Q%s:Q%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('R%s' % next_row, "{=SUM(R%s:R%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('S%s' % next_row, "{=SUM(S%s:S%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('T%s' % next_row, "{=SUM(T%s:T%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('U%s' % next_row, "{=SUM(U%s:U%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('V%s' % next_row, "{=SUM(V%s:V%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('W%s' % next_row, "{=SUM(W%s:W%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('X%s' % next_row, "{=SUM(X%s:X%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('Y%s' % next_row, "{=SUM(Y%s:Y%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('AA%s' % next_row, "{=SUM(AA%s:AA%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('AB%s' % next_row, "{=SUM(AB%s:AB%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                ws.write_formula('AC%s' % next_row, "{=SUM(AC%s:AC%s)}" % (last_line_number_str, next_row_str), table_row_right_1)
                for colnum in range(30, last_column+1):
                    columnname = colToExcel(colnum)
                    ws.write_formula('%s%s' % (columnname, next_row), "{=SUM(%s%s:%s%s)}" % (columnname,last_line_number_str, columnname, next_row_str), table_row_right_1)
                last_line_number = next_row+1

            

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
        ),
          promotion_tmp AS (
              SELECT
                pol.order_id,
                string_agg(DISTINCT promotion.name, ',') as promotion_name,
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
                bool_or(pol.non_sale) as non_sale,
                tax.price_include,
                SUM(CASE WHEN pol.product_id IN ({rounding_product_id}) and tax.price_include = True
                    THEN
                        ROUND(pol.qty * pol.price_unit, 2)
					WHEN pol.product_id IN ({rounding_product_id}) and tax.price_include = False
					Then
						ROUND( ROUND(pol.qty * pol.price_unit, 2) + ROUND( ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100) , 2), 2)
                    ELSE 0 END
                )                                                                       AS pos_rounding,
                SUM(CASE WHEN pol.product_id IN (promotion_products.discount_product_id, 
                                                 promotion_products.discount_promotion_bundle_id, 
                                                 promotion_products.discount_promotion_product_id)
                                                 and tax.price_include = False
                    THEN
                        ROUND(-1 * pol.qty * pol.price_unit, 2)
                    WHEN pol.product_id IN (promotion_products.discount_product_id, 
												promotion_products.discount_promotion_bundle_id, 
												promotion_products.discount_promotion_product_id)
												and tax.price_include = True
                    THEN
						ROUND( ROUND(-1 * pol.qty * pol.price_unit, 2) - ROUND(-1 * ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2), 2)
                    ELSE 0 END
                )                                                                        AS discount_amount,
                --SUM(CASE WHEN pol.product_id NOT IN (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
                --    THEN
                --        ROUND(pol.qty * pol.price_unit, 2)
                --    ELSE 0 END
                --)                                                                        AS amount_w_tax,
                SUM(CASE WHEN pol.product_id NOT IN (promotion_products.discount_product_id, 
                                                     promotion_products.discount_promotion_bundle_id, 
                                                     promotion_products.discount_promotion_product_id,
                                                     {rounding_product_id})
                    THEN
                        ROUND(pol.qty * pol.price_unit, 2)
                    ELSE 0 END
                )                                                                        AS amount_w_tax,
                SUM(CASE WHEN pol.product_id NOT IN (promotion_products.discount_product_id, 
                                                     promotion_products.discount_promotion_bundle_id, 
                                                     promotion_products.discount_promotion_product_id,
                                                     {rounding_product_id}) and (tax.price_include = False or tax.price_include is null) 
                    THEN
                       ROUND( ROUND(pol.qty * pol.price_unit, 2) + ROUND( ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100) , 2), 2)
                    
                    WHEN pol.product_id NOT IN (promotion_products.discount_product_id, 
                                                     promotion_products.discount_promotion_bundle_id, 
                                                     promotion_products.discount_promotion_product_id,
                                                     {rounding_product_id}) and tax.price_include = True
                    THEN
                        ROUND(pol.qty * pol.price_unit, 2)
                    
                    ELSE 0 END
                )   AS amount_with_tax,
                SUM(CASE WHEN pol.product_id IN (promotion_products.discount_product_id, 
												promotion_products.discount_promotion_bundle_id, 
												promotion_products.discount_promotion_product_id)
												and tax.price_include = False
                    THEN
                        ROUND( ROUND(-1 * pol.qty * pol.price_unit, 2) + ROUND(-1 * ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2), 2)
                    WHEN pol.product_id IN (promotion_products.discount_product_id, 
												promotion_products.discount_promotion_bundle_id, 
												promotion_products.discount_promotion_product_id)
												and tax.price_include = True
					THEN
						ROUND(-1 * pol.qty * pol.price_unit, 2)
					ELSE 0 END
                )   AS discount_with_tax_amount,
                SUM(CASE WHEN pol.product_id NOT IN (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
                    THEN
                        ROUND(ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2)
                    ELSE 0 END
                )  AS tax,
                SUM(CASE WHEN pol.product_id IN (promotion_products.discount_product_id, promotion_products.discount_promotion_bundle_id, promotion_products.discount_promotion_product_id)
                    THEN
                        ROUND(-1 * ROUND(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE THEN coalesce(tax.amount,0) / 100 ELSE 0 END) * (coalesce(tax.amount,0) / 100), 2)
                    ELSE 0 END
                ) AS tax_discount,
                string_agg(distinct staff.name,',') staff_redeem
              FROM pos_order po
                LEFT JOIN pos_order_line pol ON po.id = pol.order_id
                LEFT JOIN tax_line_amount_temp tax ON tax.pol_id = pol.id
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
              GROUP BY pol.order_id,  tax.price_include
          ),
            payment_line_tmp AS (
              SELECT
                tmp.order_id,
                string_agg(concat(tmp.payment_method, ', ', tmp.payment_amount, ',', tmp.payment_type, ',', tmp.is_rounding_method), '|') AS payment_str
              FROM
                (
                  SELECT
                    po.id            AS order_id,
                    aj.name          AS payment_method,
                    aj.payment_type  AS payment_type,
                    case when aj.is_rounding_method = True then 'is_rounding_method' else '-' end AS is_rounding_method,
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
          payment_rounding_line_tmp AS (
              SELECT
                tmp.order_id,
                sum(tmp.payment_amount) AS payment_rounding_amount
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
                      AND aj.is_rounding_method = True
                  GROUP BY po.id, aj.id
                  ORDER BY SUM(absl.amount) DESC
                ) tmp
              GROUP BY tmp.order_id
          )
        SELECT
          bmoo.name                                                                   outlet, --index 0
          bmoo.code                                                                   outlet_code, --index 1
          bmoo.id                                                                     outlet_id, --index 2
          region.name                                                                 region, --index 3
          outlet_type.name                                                            Asset_Type, --index 4
          outlet_type_1.name                                                          location_type, --index 5
          ho.outlet_type, --index 6
          ho.status                                                                   outlet_status, --index 7
          rp_1.name                                                                   Regional_Manager, --index 8
          rp_2.name                                                                   Area_Manager, --index 9
          ps.name                                                                     session_name, --index 10
          to_char(ps.start_at, 'YYYY-MM-DD HH24:MI:SS') start_at, --index 11
          to_char(ps.stop_at, 'YYYY-MM-DD HH24:MI:SS')  stop_at, --index 12
          rp_se.name                                                                  pos_person, --index 13
          rp_sp.name                                                                  sale_person, --index 14
          date(po.date_order)                           order_date, --index 15
          to_char(po.date_order, 'HH24:MI:SS')          order_time, --index 16
          po.invoice_no, --index 17
          po.name                                                                     Order_Ref, --index 18
          po.pos_reference, --index 19
          po.id                                                                       order_po_id, --index 20
          promotion_tmp.promotions, --index 21
          order_line_tmp.discount_amount    AS                                        discount_amount, --index 22
          order_line_tmp.amount_w_tax, --index 23
          order_line_tmp.tax, --index 24
          order_line_tmp.tax_discount, --index 25
          order_line_tmp.pos_rounding, --index 26
          order_line_tmp.non_sale, --index 27
          payment_line_tmp.payment_str, --index 28
          po.vouchers AS voucher_codes, --index 29
          po.note AS remark, --index 30
          po.is_refund as is_refund, --index 31
          po.is_refunded as is_refunded, --index 32
          po.tax_adjustment as tax_adjustment, --index 33
          order_line_tmp.price_include, --index 34
          payment_rounding_line_tmp.payment_rounding_amount as payment_rounding_amount, --index 35
          order_line_tmp.amount_with_tax, --index 36
          order_line_tmp.discount_with_tax_amount, --index 37
          aaa.name as analytic_account_name, --index 38
          rcs_area.name as area, --index 39
		  rcs_parent_area.name as parent_area, --index 40
		  order_customer.name as customer_name, --index 41
		  rp_pic1.name, --index 42
		  rp_pic2.name, --index 43
		  rp_pic3.name, --index 44
		  order_line_tmp.staff_redeem, --index 45
		  promotion_tmp.promotion_name, --index 46
		  po.third_party_id --index 47
        FROM pos_order po
          LEFT JOIN get_history_outlet(po.outlet_id, po.date_order) ho ON po.outlet_id = ho.o_id
          INNER JOIN br_multi_outlet_outlet bmoo ON po.outlet_id = bmoo.id
          LEFT JOIN account_analytic_account aaa on aaa.id = bmoo.analytic_account_id 
          LEFT JOIN res_country_state rcs_area on rcs_area.id = ho.area 
          LEFT JOIN res_country_state rcs_parent_area on rcs_parent_area.id = rcs_area.parent_id
          LEFT JOIN res_partner order_customer on  order_customer.id = po.partner_id 
          LEFT JOIN res_users ru_pic1 on ru_pic1.id = ho.pic1
          LEFT JOIN res_partner rp_pic1 ON rp_pic1.id = ru_pic1.partner_id
		  LEFT JOIN res_users ru_pic2 on ru_pic2.id = ho.pic2
		  LEFT JOIN res_partner rp_pic2 ON rp_pic2.id = ru_pic2.partner_id
		  LEFT JOIN res_users ru_pic3 on ru_pic3.id = ho.pic3
		  LEFT JOIN res_partner rp_pic3 ON rp_pic3.id = ru_pic3.partner_id
          LEFT JOIN br_multi_outlet_region_area region ON region.id = ho.region
          LEFT JOIN br_multi_outlet_outlet_type outlet_type ON outlet_type.id = ho.asset_type
          LEFT JOIN br_multi_outlet_outlet_type outlet_type_1 ON outlet_type_1.id = ho.location_type
          LEFT JOIN res_users ru_1 ON ho.region_ma = ru_1.id
          LEFT JOIN res_partner rp_1 ON rp_1.id = ru_1.partner_id
          LEFT JOIN res_users ru_2 ON ho.area_ma = ru_2.id
          LEFT JOIN res_partner rp_2 ON rp_2.id = ru_2.partner_id
          LEFT JOIN pos_session ps ON ps.id = po.session_id
          LEFT JOIN res_users res_se ON ps.user_id = res_se.id
          LEFT JOIN res_partner rp_se ON res_se.partner_id = rp_se.id
          LEFT JOIN res_users res_sp ON po.user_id = res_sp.id
          LEFT JOIN res_partner rp_sp ON res_sp.partner_id = rp_sp.id
          LEFT JOIN order_line_tmp ON order_line_tmp.order_id = po.id
          LEFT JOIN payment_line_tmp ON payment_line_tmp.order_id = po.id
          LEFT JOIN payment_rounding_line_tmp ON payment_rounding_line_tmp.order_id = po.id
          LEFT JOIN promotion_tmp ON promotion_tmp.order_id = po.id
        WHERE po.outlet_id IN
            (SELECT br_multi_outlet_outlet_id
             FROM br_multi_outlet_outlet_res_users_rel brrel
             WHERE brrel.res_users_id = {user_id_report})
            AND {sql_oulet_string}
            AND po.date_order >= '{start_date}'
            AND po.date_order <= '{end_date}'
        ORDER BY {orderby};
        '''.format(**args)
        self.env.cr.execute(sql)
        # print "sql sale new",sql
        data = self.env.cr.fetchall()
        return data

    def get_workbook_options(self):
        return {'constant_memory': True}


br_sales_order_report('report.br_sales_report.br_sales_order_report', 'br.sales.report')



