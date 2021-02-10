# --*-- coding: utf-8 --*--

from openerp import fields, models, api, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
import pytz
from datetime import datetime

class sales_raw_data(models.TransientModel):
    _name = 'sales.raw.data'

    start_date = fields.Date(string=_("Start date"))
    end_date = fields.Date(string=_("End date"))
    outlet_ids = fields.Many2many(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_point_of_sale.sales_raw_data')


class sales_raw_data_report(ReportXlsx):
    _name = 'report.br_point_of_sale.sales_raw_data'

    def convert_timezone(self, from_tz, to_tz, date):
        from_tz = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone(from_tz))
        to_tz = from_tz.astimezone(pytz.timezone(to_tz))
        return to_tz.strftime("%Y-%m-%d %H:%M:%S")


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
        outlet_names = []
        outlet_ids = []
        for x in report.outlet_ids:
            outlet_names.append(x.name)
            outlet_ids.append(x.id)

        # SET COLUMNS'S WIDTH
        ws.set_column(0, 0, 11)
        col_width = {
            30: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
            0: [11]
        }
        for w in col_width:
            for c in col_width[w]:
                ws.set_column(c, c, w)


        # REPORT'S HEADER
        ws.write('A1', u'Start Date', bold)
        ws.write('A2', u'End Date', bold)
        ws.write('A3', u'Outlet(s)', bold)
        ws.write('B1', report.start_date)
        ws.write('B2', report.end_date)
        ws.write('B3', ', '.join(outlet_names))

        # ------------------- Header -------------------
        ws.write('A5', 'Outlet', table_header)
        ws.write('B5', 'Order No', table_header)
        ws.write('C5', 'Date Order', table_header)
        ws.write('D5', 'Product', table_header)
        ws.write('E5', 'Menu Name', table_header)
        ws.write('F5', 'Menu Number', table_header)
        ws.write('G5', 'Menu Category', table_header)
        ws.write('H5', 'Internal Category', table_header)
        ws.write('I5', 'UOM', table_header)
        ws.write('J5', 'Price List', table_header)
        ws.write('K5', 'Qty', table_header)
        ws.write('L5', 'Tax', table_header)
        ws.write('M5', 'Price Unit', table_header)
        ws.write('N5', 'Sub Total', table_header)
        ws.write('O5', 'Promotion', table_header)
        ws.write('P5', 'Discount Amount', table_header)
        ws.write('Q5', 'Customer', table_header)
        ws.write('R5', 'Analytic Account', table_header)
        ws.write('S5', 'State', table_header)
        ws.write('T5', 'Area', table_header)
        ws.write('U5', 'Outlet Type 1', table_header)
        ws.write('V5', 'Outlet Type 2', table_header)
        ws.write('W5', 'Sale Man', table_header)
        ws.write('X5', 'Account Bank Statement', table_header)
        ws.write('Y5', 'Promotion Category', table_header)

        # FILL DATA
        # utc_start_date = self.convert_timezone(self.env.user.tz or 'UTC', 'UTC', report.start_date + ' 00:00:00')
        # utc_end_date = self.convert_timezone(self.env.user.tz or 'UTC', 'UTC', report.end_date + ' 23:59:59')
        report_data = self.get_report_data({
            'outlet_ids': ', '.join([str(x) for x in outlet_ids]) if outlet_ids else 'NULL',
            'start_date': report.start_date,
            'end_date': report.end_date,
            'tz': self.get_timezone_offset()
        })
        row = 6
        for line in report_data:
            ws.write('A%s'% row, line['outlet'], table_row_left)
            ws.write('B%s'% row, line['order_no'], table_row_left)
            ws.write('C%s'% row, line['date_order'], table_row_left)
            ws.write('D%s'% row, line['product'], table_row_left)
            ws.write('E%s'% row, line['menu_name'], table_row_left)
            ws.write('F%s'% row, line['menu_number'], table_row_left)
            ws.write('G%s'% row, line['menu_category'], table_row_left)
            ws.write('H%s'% row, line['internal_category'], table_row_left)
            ws.write('I%s'% row, line['standard_uom'], table_row_left)
            ws.write('J%s'% row, line['pricelist'], table_row_left)
            ws.write('K%s'% row, line['qty'], table_row_right)
            ws.write('L%s'% row, line['tax'], table_row_right)
            ws.write('M%s'% row, line['price_unit'], table_row_right)
            ws.write('N%s'% row, line['sub_total'], table_row_right)
            ws.write('O%s'% row, line['promotion'], table_row_left)
            ws.write('P%s'% row, line['discount_amount'], table_row_right)
            ws.write('Q%s'% row, line['customer'], table_row_left)
            ws.write('R%s'% row, line['analytic_account'], table_row_left)
            ws.write('S%s'% row, line['state'], table_row_left)
            ws.write('T%s'% row, line['area'], table_row_left)
            ws.write('U%s'% row, line['outlet_type1_name'], table_row_left)
            ws.write('V%s'% row, line['outlet_type2_name'], table_row_left)
            ws.write('W%s'% row, line['saleman'], table_row_left)
            ws.write('X%s'% row, line['account_bank'], table_row_left)
            ws.write('Y%s'% row, line['promotion_categ'], table_row_left)
            row += 1

    def get_report_data(self, args):
        sql = """
        SELECT
            orderline.id                         AS orderline_id,
            outlet.name                          AS outlet,
            pos.name                             AS order_no,
            (pos.date_order + interval '+08 hour') :: DATE  AS date_order,
            pp_item.name_template                AS product,
            pp_master.name_template              AS menu_name,
            orderline_master.name                AS menu_number,
            menu_categ.name                      AS menu_category,
            product_category.name                AS internal_category,
            uom.name                             AS standard_uom,
            pricelist.name                       AS pricelist,
            orderline.qty,
            ROUND(
              CAST((orderline.price_unit / (1 + (SUM(tax.amount) / 100))) * (SUM(tax.amount) / 100) * orderline.qty
                   AS
                   NUMERIC), 5)                AS tax,
            orderline.price_unit,
            orderline.price_unit * orderline.qty AS sub_total,
            string_agg(promotion.name, ', ')     AS promotion,
            orderline.discount_amount,
            customer.name                        AS customer,
            aa_account.name                      AS analytic_account,

            res_country_state.name               AS state,
            br_multi_outlet_region_area.name     AS area,
            type1.name                           AS outlet_type1_name,
            type2.name                           AS outlet_type2_name,
            ru.login                             AS saleman,
            string_agg(absl.name, ', ') AS account_bank,
            br_promotion_category.name           AS promotion_categ
        FROM pos_order pos
            LEFT JOIN res_partner AS customer ON customer.id = pos.partner_id
            INNER JOIN pos_order_line orderline ON orderline.order_id = pos.id
            LEFT JOIN br_pos_order_line_master orderline_master ON orderline.master_id = orderline_master.id
            INNER JOIN br_multi_outlet_outlet outlet ON pos.outlet_id = outlet.id
            LEFT JOIN account_analytic_account aa_account ON outlet.analytic_account_id = aa_account.id
            LEFT JOIN product_product pp_item ON pp_item.id = orderline.product_id
            LEFT JOIN product_template pt_item ON pp_item.product_tmpl_id = pt_item.id
            LEFT JOIN product_product pp_master ON pp_master.id = orderline_master.product_id
            LEFT JOIN br_menu_category menu_categ ON menu_categ.id = pp_master.menu_category_id
            LEFT JOIN product_template pt_master ON pp_master.product_tmpl_id = pt_master.id
            LEFT JOIN product_category ON pt_item.categ_id = product_category.id
            LEFT JOIN product_uom uom ON pt_item.uom_id = uom.id
            LEFT JOIN product_pricelist pricelist ON outlet.pricelist_id = pricelist.id
            LEFT JOIN account_tax_pos_order_line_rel
            ON orderline.id = account_tax_pos_order_line_rel.pos_order_line_id
            LEFT JOIN account_tax tax ON account_tax_pos_order_line_rel.account_tax_id = tax.id
            LEFT JOIN stock_move sm ON sm.name = orderline.name
            LEFT JOIN pos_order_line_promotion_default_rel
            ON orderline.id = pos_order_line_promotion_default_rel.pos_order_line_id
            LEFT JOIN br_bundle_promotion promotion
            ON pos_order_line_promotion_default_rel.promotion_id = promotion.id

            LEFT JOIN res_country_state ON outlet.state_id = res_country_state.id
            LEFT JOIN br_multi_outlet_region_area ON outlet.region_area_id = br_multi_outlet_region_area.id
            LEFT JOIN br_multi_outlet_outlet_type type1 ON outlet.type1 = type1.id
            LEFT JOIN br_multi_outlet_outlet_type type2 ON outlet.type2 = type2.id
            LEFT JOIN res_users ru ON pos.user_id = ru.id
            LEFT JOIN account_bank_statement_line absl ON pos.id = absl.pos_statement_id
            LEFT JOIN br_promotion_category ON promotion.promotion_category_id = br_promotion_category.id
        WHERE
        CASE
            WHEN ({outlet_ids}) IS NOT NULL THEN outlet.id IN ({outlet_ids}) ELSE 1 = 1
        END
        AND (date_order + interval '{tz} hour') :: DATE >= '{start_date}' AND (date_order + interval '{tz} hour') :: DATE <= '{end_date}'
        GROUP BY orderline.id,
            outlet.name,
            pos.id,
            pos.name,
            pos.date_order,
            pp_item.id,
            pt_item.type,
            pp_master.id,
            orderline_master.name,
            menu_categ.name,
            product_category.name,
            sm.id,
            uom.name,
            pricelist.name,
            tax.id,
            customer.id,
            aa_account.id,
            res_country_state.id,
            br_multi_outlet_region_area.id,
            --    br_bundle_promotion.id,
            br_promotion_category.id,
            type1.id,
            type2.id,
            ru.login
        """.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_workbook_options(self):
        return {}


sales_raw_data_report('report.br_point_of_sale.sales_raw_data', 'sales.raw.data')
