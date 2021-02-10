from openerp import fields, models, api, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
import pytz
from datetime import datetime, timedelta
import re

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class report_stock_transfer_note(ReportXlsx):
    _name = 'report.br_stock.stock_transfer_note'

    @api.multi
    def render_html(self, data):
        pass

    def convert_timezone(self, from_tz, to_tz, date):
        from_tz = datetime.strptime(date, DATE_FORMAT).replace(tzinfo=pytz.timezone(from_tz))
        to_tz = from_tz.astimezone(pytz.timezone(to_tz))
        return to_tz.strftime(DATE_FORMAT)

    def generate_xlsx_report(self, wb, data, report):
        # DEFINE FORMATS

        # Font style
        font = 'Palatino Linotype'

        bold_right_big = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'right',
            'valign': 'top',
            'font_name': font,
            'font_size': 20,

        })
        bold_left_big = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'left',
            'valign': 'top',
            'font_name': font,
            'font_size': 20,

        })
        bold_text = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'valign': 'top',
            'font_name': font,
        })

        bold = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'valign': 'top',
            'font_name': font,
        })

        bold_right = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'right',
            'valign': 'top',
            'font_name': font,
        })
        bold_left = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'left',
            'valign': 'top',
            'font_name': font,
        })
        normal = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'top',
            'num_format': '#,##0.00',
            'font_name': font
        })
        right = wb.add_format({
            'text_wrap': True,
            'align': 'right',
            'valign': 'top',
            'num_format': '#,##0.00',
            'font_name': font

        })
        left = wb.add_format({
            'text_wrap': True,
            'align': 'left',
            'valign': 'top',
            'font_name': font

        })

        center = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'top',
            'font_name': font,
        })

        # Table style
        table_header = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'center',
            'valign': 'top',
            'border': 1,
            'font_name': font,
        })

        table_row_left = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'top',
            'border': 1,
            'font_name': font,
        })

        table_bottomless_left = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'top',
            'font_name': font,
            'top': 1,
            'left': 1,
            'right': 1
        })

        table_bottomless_center = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'top',
            'top': 1,
            'left': 1,
            'right': 1,
            'font_name': font,
        })

        table_row_center = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'top',
            'border': 1,
            'font_name': font,
        })

        table_bottomless_right = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'top',
            'top': 1,
            'left': 1,
            'right': 1,
            'num_format': '#,##0.00',
            'font_name': font,
        })

        table_row_right = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'top',
            'border': 1,
            'num_format': '#,##0.00',
            'font_name': font,
        })

        # Left and right border
        table_border_right = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'top',
            'font_name': font,
            'right': 1
        })

        table_border_left = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'top',
            'font_name': font,
            'left': 1
        })

        table_border_left_right = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'top',
            'font_name': font,
            'left': 1,
            'right': 1
        })
        table_border_left_right2 = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'top',
            'font_name': font,
            'left': 1,
            'right': 1
        })

        for picking in report:
            ws_name = re.sub('[^A-Za-z0-9]', '|', picking.name)
            ws = wb.add_worksheet(ws_name)

            # SET PAPERS
            wb.formats[0].font_name = 'Palatino Linotype'
            wb.formats[0].font_size = 11
            ws.set_paper(12)
            ws.center_horizontally()
            ws.set_margins(left=0.28, right=0.28, top=0.5, bottom=0.5)
            ws.fit_to_pages(1, 0)
            ws.set_portrait()
            ws.fit_to_pages(1, 1)

            # SET COLUMNS'S WIDTH
            ws.set_column(0, 0, 6)
            ws.set_column(1, 1, 30)
            ws.set_column(2, 2, 30)
            ws.set_column(3, 3, 15)
            ws.set_column(4, 4, 25)
            ws.set_column(5, 5, 8)
            ws.set_column(6, 6, 12)

            # SET ROW's HEIGHT
            ws.set_row(0, 25)
            ws.set_row(2, 66)
            ws.set_row(12, 80)
            # REPORT'S HEADER
            ws.merge_range('D1:G1', "Stock Transfer Note", bold_right_big)
            company = self.env.user.company_id
            company_address = [company.street, company.street2, company.zip, company.state_id.name]
            ws.merge_range('A1:C1', company.name, bold_left_big)
            ws.merge_range('A2:C2', company.company_registry, normal)
            ws.merge_range('A3:C3', "%s\n%s\n%s" % (
                ", ".join([x for x in company_address if x]),
                'Tel: %s      Fax: %s' % (company.phone, company.fax),
                'GST Reg.No: %s' % (company.vat or "")), normal)
            ws.write("E5", "Stock Transfer Note No:", bold_left)
            ws.merge_range("F5:G5", picking.name, normal)
            # ws.write("F5", picking.name, right)
            ws.write("E6", "Transfer Date:", bold_left)
            # ws.write("F6", picking.min_date)
            if picking.min_date:
                do_date = datetime.strptime(picking.min_date, DATE_FORMAT) + timedelta(hours=8)
                do_date = do_date.strftime(DATE_FORMAT)
            else:
                do_date = ""
            ws.merge_range("F6:G6", do_date, normal)

            # set Driver, Vehicle and RQ Number
            ws.write("E7", "Driver:", bold_left)
            ws.write("E8", "Vehicle:", bold_left)
            ws.write("E9", "RQ Number:", bold_left)
            if picking.driver:
                ws.merge_range("F7:G7", picking.driver.display_name, normal)
            else:
                ws.merge_range("F7:G7", "", normal)
            if picking.vehicle:
                ws.merge_range("F8:G8", picking.vehicle.name, normal)
            else:
                ws.merge_range("F8:G8", "", normal)
            if picking.request_id:
                ws.merge_range("F9:G9", picking.request_id.name, left)
            else:
                ws.merge_range("F9:G9", "", left)

            ws.write('A12', 'From:', bold)

            if picking.picking_type_id and picking.picking_type_id.warehouse_id:
                warehouse = picking.picking_type_id.warehouse_id
                wh_partner = warehouse.partner_id
                wh_partner_address = [wh_partner.city, wh_partner.state_id.name if wh_partner.state_id else False,
                                      wh_partner.zip]
                wh_partner_address_str = ", ".join([x for x in wh_partner_address if x])
                ws.merge_range('B12:C12', warehouse.name, normal)
                ws.merge_range('B13:C13',
                               "%s\n%s\n%s" % (wh_partner.street or "", wh_partner_address_str, wh_partner.phone or ''),
                               normal)
            ws.write('E12', 'Deliver To:', bold)
            if picking.location_dest_id and picking.location_dest_id.br_address:
                ws.merge_range('F12:G12', picking.location_dest_id.warehouse_id.name, normal)
                ws.merge_range('E13:G13', picking.location_dest_id.br_address, normal)
            else:
                partner = picking.partner_id
                partner_address = [partner.city, partner.state_id.name if partner.state_id else False, partner.zip]
                partner_address_str = ", ".join([x for x in partner_address if x])
                ws.merge_range('F12:G12',
                               partner.name if not partner.parent_id and partner.name else partner.parent_id.name if partner.parent_id else "",
                               normal)
                ws.merge_range('E13:G13',
                               "%s \n%s\n %s" % (partner.street or "", partner_address_str, partner.phone or ''), normal)

            # ------------------- Header -------------------
            row = 16
            ws.write('A%s' % row, 'No', table_header)
            ws.write('B%s' % row, 'Description', table_header)
            ws.write('C%s' % row, 'Vendor', table_header)
            ws.write('D%s' % row, 'Lot', table_header)
            ws.write('E%s' % row, 'Lot Qty', table_header)
            ws.write('F%s' % row, 'Total Qty', table_header)
            ws.write('G%s' % row, 'UOM', table_header)
            row += 1
            i = 1
            sum_start = row
            for line in picking.pack_operation_ids:
                # if pack has more than 2 lots, first line should not have bottom border
                if len(line.pack_lot_ids) > 1:
                    table_left = table_bottomless_left
                    table_right = table_bottomless_right
                    table_center = table_bottomless_center
                else:
                    table_left = table_row_left
                    table_right = table_row_right
                    table_center = table_row_center

                ws.write('A%s' % row, i, table_center)
                product = line.product_id
                ws.write('B%s' % row, "[%s] %s" % (
                    product.default_code, product.name_template) if product.default_code else product.name_template,
                         table_left)
                pack_row = row
                ws.write('C%s' % row, line.vendor_id.name, table_left)
                ws.write('D%s' % row, "", table_center)
                ws.write('E%s' % row, "", table_center)
                for lot in line.pack_lot_ids:
                    if pack_row - row > 0:
                        ws.write('A%s' % pack_row, "", table_border_left_right)
                        ws.write('C%s' % pack_row, "", table_border_left_right)
                        ws.write('D%s' % pack_row, lot.lot_id.name, table_border_left_right)
                        ws.write('E%s' % pack_row, "%s / %s" % (lot.qty, lot.qty_todo), table_border_left_right2)

                        ws.write('F%s' % pack_row, "", table_border_right)
                        ws.write('G%s' % pack_row, "", table_border_right)
                    else:
                        ws.write('D%s' % pack_row, lot.lot_id.name, table_center)
                        ws.write('E%s' % pack_row, "%s / %s" % (lot.qty, lot.qty_todo), table_right)
                    pack_row += 1

                ws.write('F%s' % row, line.qty_done, table_right)
                ws.write('G%s' % row, line.product_uom_id.name, table_center)
                row += (pack_row - row) + 1 if pack_row == row else (pack_row - row)
                i += 1
            sum_end = row
            ws.merge_range("A%s:C%s" % (row, row), "Received the above goods in good order & condition", normal)
            row += 1
            uoms = ["PACKET", "SPECIAL"]
            for uom in uoms:
                ws.write_formula('F%s' % row,
                                 '=SUMIF(G%s:G%s,"%s", F%s:F%s)' % (sum_start, sum_end, uom, sum_start, sum_end))
                ws.write("G%s" % row, '%sS' % uom, normal)
                row += 1
            ws.write('F%s' % row, picking.fulfill_tub_total)
            ws.write('G%s' % row, "TUBS", normal)
            row += 1
            ws.write('F%s' % row, picking.fulfill_carton_total)
            ws.write('G%s' % row, "FULL CTNS", normal)
            row += 1
            ws.write('F%s' % row, picking.fulfill_cake_total)
            ws.write('G%s' % row, "CAKES", normal)
            row += 1
            ws.write('G%s' % row, "MIXED CTNS", normal)
            row += 5
            ws.merge_range("A%s:B%s" % (row, row), "Driver's Signature", center)
            ws.merge_range("E%s:G%s" % (row, row), "Picker/Packer's Signature", center)
            row += 1
            ws.merge_range("A%s:B%s" % (row, row), picking.driver.display_name, center)
            ws.merge_range("E%s:G%s" % (row, row), picking.packer.display_name, center)
            row += 5
            ws.merge_range("A%s:B%s" % (row, row), "Customer's Stamp and Signature", center)
            ws.merge_range("E%s:G%s" % (row, row), "For Golden Scoop Sdn. Bhd.", center)

    def get_workbook_options(self):
        return {}


report_stock_transfer_note('report.br_stock.stock_transfer_note', 'stock.picking')
