# -*- coding: utf-8 -*-

from collections import defaultdict
import pytz

from openerp import api, fields, models
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from datetime import datetime, date
from openerp.exceptions import UserError
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT

import time


DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def convert_timezone(from_tz, to_tz, dt):
    from_tz = pytz.timezone(from_tz).localize(datetime.strptime(dt, DATETIME_FORMAT))
    to_tz = from_tz.astimezone(pytz.timezone(to_tz))
    return to_tz.strftime(DATETIME_FORMAT)


class stock_inventory_wizard(models.TransientModel):
    _name = 'stock.inventory.wizard'

    @api.model
    def _get_end_date(self):
        today = date.today()
        last_date = today + relativedelta(day=1, months=1, days=-1)
        return last_date

    warehouse_ids = fields.Many2many(
                        'stock.warehouse',
                        string='Warehouse')
    start_date = fields.Date('Start Date', required=True, default=lambda *a: time.strftime('%Y-%m-01'))
    end_date = fields.Date('End Date', required=True, default=_get_end_date)
    product_categ_ids = fields.Many2many(
                        comodel_name='product.category',
                        string='Product Categs')
    product_ids = fields.Many2many(
                        comodel_name='product.product',
                        string='Product')
    is_lot = fields.Selection([
                ('yes', 'Yes'),
                ('no', 'No')], string='Lot No')
    report_type = fields.Selection([
                    ('inventory_gl_report', 'Inventory Gain Loss Report'),
                    ('inventory_damage_report', 'Inventory Damage Report')
                    ], string='Report Type')
    inv_categ_uom_ids = fields.One2many('stock.inventory.categ.uom', 'inv_wizard_id', string='Categires UoM')
    uom_type = fields.Selection([
                    ('standard', 'Standard'),
                    ('purchase', 'Purchase UoM'),
                    ('distribution', 'Distribution'),
                    ('storage', 'Storage'),
                    ], string='UoM Type', required=True, default='standard')
    # test = fields.Boolean('Test')

    hq_wh = fields.Boolean("HQ Warehouses")
    outlet_wh = fields.Boolean("Outlet Warehouses")

    @api.onchange('hq_wh', 'outlet_wh')
    def onchange_hq_wh_and_outlet_wh(self):
        res = {'domain': {'warehouse_ids': [], 'location_ids': []}}
        if self.hq_wh and not self.outlet_wh:
            res['domain']['warehouse_ids'] = [('is_main_warehouse', '=', True)]
        elif not self.hq_wh and self.outlet_wh:
            res['domain']['warehouse_ids'] = [('is_main_warehouse', '=', False)]
        return res

    @api.multi
    def action_print(self):
        # perform flush date checking before printing the report
        self.check_flush_date()
        return self.env['report'].get_action(self, 'stock_inventory_adj.stock_inventory_adj_report')

    @api.multi
    def check_flush_date(self):
        """
        Make sure the start date of the report is greater than latest flush
        date
        """
        for res in self:
            # get the latest flush date
            latest_flush_date = self.env['stock.flush.date'].search(
                [], order='flush_date desc', limit=1)
            # check the report start date
            if latest_flush_date:
                flush_date = convert_timezone(
                    'UTC',
                    self.env.user.tz or 'UTC',
                    latest_flush_date.flush_date).split(' ')[0]
                if res.start_date and \
                        datetime.strptime(res.start_date,
                                          DEFAULT_SERVER_DATE_FORMAT) < \
                        datetime.strptime(flush_date,
                                          DEFAULT_SERVER_DATE_FORMAT):
                    raise UserError(('Kindly select a start date greater '
                                     'than the flush date.\n Flush Date: '
                                     '%s') % flush_date)
            return True


class stock_inventory_categ_uom(models.TransientModel):
    _name = 'stock.inventory.categ.uom'

    uom_categ_id = fields.Many2one('product.category', string='Category')
    uom_type = fields.Selection([
                    ('standard', 'Standard'),
                    ('purchase', 'Purchase UoM'),
                    ('distribution', 'Distribution'),
                    ('storage', 'Storage'),
                    ], string='UoM Type')
    inv_wizard_id = fields.Many2one('stock.inventory.wizard', string='Wizard')


class stock_inventory_adj_report(ReportXlsx):
    _name = 'report.stock_inventory_adj.stock_inventory_adj_report'

    def generate_xlsx_report(self, wb, data, report):
        Product = self.env['product.product']
        ProductCateg = self.env['product.category']
        StockInventoryUomCateg = self.env['stock.inventory.categ.uom']

        ws = wb.add_worksheet('Inventory Details Report')
        self.set_paper(wb, ws)
        self.styles = self.get_report_styles(wb)
        self.set_header(ws, report)
        # domain = self.get_domain(report)
        start_date = report.start_date + ' 00:00:00'
        end_date = report.end_date + ' 23:59:59'

        warehouse_ids = []
        if report.warehouse_ids:
            warehouse_ids = report.warehouse_ids.ids

        product_ids = []
        product_categs = self.env['product.category']

        # if report.product_categ_ids:
        product_categs = report.product_categ_ids
        for categ in product_categs:
            categ_ids = ProductCateg.search([('id', 'child_of', categ.id)])
            products = report.product_ids.filtered(lambda r: r.categ_id in categ_ids)
            if products:
                product_ids += products.ids
            else:
                products = Product.search([('categ_id', 'in', categ_ids.ids)])
                product_ids += products.ids

        if report.product_ids:
            product_ids = report.product_ids.ids

        # TODO: This code for if not any categories selected
        # else:
        #     # product_categs = report.product_categ_ids
        #     categ_parents = ProductCateg.search([('parent_id', '=', False)], order='id')
        #     if categ_parents:
        #         parent_child_categs = ProductCateg.search([
        #             ('parent_id', 'in', categ_parents.ids)], order='id')
        #         # categ_ids = categs.ids

        #         product_categs += parent_child_categs
        #         for categ_parent in parent_child_categs:
        #             categs = ProductCateg.search([('id', 'child_of', categ_parent.id)], order='id')
        #             products = report.product_ids.filtered(lambda r: r.categ_id in categs)
        #             if products:
        #                 product_ids += products.ids
        #             else:
        #                 products = Product.search([('categ_id', 'in', categs.ids)])
        #                 product_ids += products.ids

        for cat in product_categs:
            child_categ_ids = ProductCateg.search([('id', 'child_of', cat.id)])
            if not report.inv_categ_uom_ids:
                for child_categ in child_categ_ids:
                    self.env.cr.execute("""
                        INSERT INTO inventory_categ_uom_type (uom_categ_id, uom_type, parent_categ_id)
                            values(%s, %s, %s)""", (child_categ.id, report.uom_type, cat.id))
            else:
                # if report.inv_categ_uom_ids and len(report.inv_categ_uom_ids) == 1 and not report.inv_categ_uom_ids.uom_categ_id:
                #     uom_type = report.inv_categ_uom_ids.uom_type
                #     for child_categ in child_categ_ids:
                #         self.env.cr.execute("""
                #             INSERT INTO inventory_categ_uom_type (uom_categ_id, uom_type, parent_categ_id)
                #                 values(%s, %s, %s)""", (child_categ.id, uom_type, cat.id))
                # else:
                if report.inv_categ_uom_ids:
                    line = StockInventoryUomCateg.search([
                        ('inv_wizard_id', '=', report.id),
                        ('uom_categ_id', '=', cat.id)
                    ], limit=1)
                    uom_type = line.uom_type if line else report.uom_type
                    for child_categ in child_categ_ids:
                        self.env.cr.execute("""
                            INSERT INTO inventory_categ_uom_type (uom_categ_id, uom_type, parent_categ_id)
                                values(%s, %s, %s)""", (child_categ.id, uom_type, cat.id))

        sql_product_string = '1=1'
        if product_ids:
            sql_product_string = 'product.id in ' + str(product_ids).replace('[', '(').replace(']', ')')

        sql_warehouse_string = '1=1'
        if warehouse_ids:
            sql_warehouse_string = 'warehouse.id in ' + str(warehouse_ids).replace('[', '(').replace(']', ')')

        credentials = {
            'start_date': start_date,
            'end_date': end_date,
            'company_id': self.env.user.company_id.id,
            'sql_warehouse_string': sql_warehouse_string,
            'sql_product_string': sql_product_string
        }
        report_data = self.get_data(credentials)
        self.bind_data(ws, report_data, report)

    def set_paper(self, wb, ws):
        # SET PAPERS
        wb.formats[0].font_name = 'Times New Roman'
        wb.formats[0].font_size = 11
        ws.set_paper(9)
        ws.center_horizontally()
        ws.set_margins(left=0.28, right=0.28, top=0.5, bottom=0.5)
        ws.fit_to_pages(1, 0)
        ws.set_landscape()
        ws.fit_to_pages(1, 1)
        ws.set_column(0, 45, 30)

    def get_report_styles(self, wb):
        styles = {}
        styles['bold_right_big'] = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })

        styles['bold'] = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })

        styles['right'] = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman'
        })

        styles['center'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })

        styles['date_left'] = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy',
        })

        styles['table_header'] = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
        })

        styles['table_row_left'] = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
        })

        styles['table_row_right'] = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })

        styles['table_row_center'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })

        styles['table_row_date'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy',
        })

        styles['table_row_time'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'hh:mm:ss',
        })

        styles['table_row_datetime'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy hh:mm:ss',
        })
        return styles

    def set_header(self, ws, report):
        ws.write('B1', u'Inventory Adjustment Summary', self.styles['bold'])

        ws.write('A3', u'Warehouse(s)', self.styles['bold'])
        ws.write('B3', ', '.join([w.name for w in report.warehouse_ids]))

        ws.write('A4', u'Start Date', self.styles['bold'])
        ws.write_datetime('B4', datetime.strptime(report.start_date, DATE_FORMAT), self.styles['date_left'])
        ws.write('A5', u'End Date', self.styles['bold'])
        ws.write_datetime('B5', datetime.strptime(report.end_date, DATE_FORMAT), self.styles['date_left'])
        ws.write('A6', u'Product Category(s)', self.styles['bold'])
        if report.product_categ_ids:
            categs = ', '.join([l.complete_name for l in report.product_categ_ids])
        else:
            categs = 'All'
        ws.write('B6', categs)
        ws.write('A7', u'Product(s)', self.styles['bold'])

        if report.product_ids:
            products = ', '.join([l.name for l in report.product_ids])
        else:
            products = 'All'
        ws.write('B7', products)

        ws.write('A8', u'Report Type', self.styles['bold'])
        ws.write('B8', report.report_type)

    def get_domain(self, report):
        return {}

    def get_data(self, args):
        query = """
             WITH inventory AS (
                SELECT
            st.id AS st_id,
            warehouse.id AS warehouse_id, warehouse.name AS warehouse_name, st.location_id AS location_id,
            warehouse.gain_src_location_id AS gain_src_location_id, warehouse.loss_src_location_id AS loss_src_location_id,
            warehouse.gain_dest_location_id AS gain_dest_location_id, warehouse.loss_dest_location_id AS loss_dest_location_id,
            st.company_id
                FROM
                    stock_inventory st
                    LEFT JOIN stock_warehouse warehouse ON warehouse.lot_stock_id = st.location_id
                WHERE
                    st.accounting_date >= '{start_date}'
                    AND st.accounting_date <= '{end_date}'
                    AND st.company_id = {company_id}
                    AND st.stock_count_type = 'official'
                    AND st.state in ('done','1st_degree','2nd_degree','no_case')
                    AND {sql_warehouse_string}
                GROUP BY warehouse.id, st.location_id, st_id
            )
            SELECT
                inventory.warehouse_id AS warehouse_id,
                inventory.warehouse_name AS warehouse_name,
                product_category.name AS categ_name,
                invent_categ.parent_categ_id AS parent_categ_id,
                ROUND(CAST((CASE WHEN st_move.location_id = inventory.gain_src_location_id AND st_move.location_dest_id = inventory.gain_dest_location_id THEN SUM(COALESCE((quant.cost * quant.qty), 0.0))
                    ELSE 0.0
                END ) AS NUMERIC), 2) AS gain_cost,
                ROUND(CAST((CASE WHEN  st_move.location_id = inventory.loss_src_location_id AND st_move.location_dest_id = inventory.loss_dest_location_id THEN SUM(COALESCE((quant.cost * quant.qty), 0.0))
                    ELSE 0.0
                END) AS NUMERIC), 2) AS loss_cost,

                CASE WHEN st_move.location_id = inventory.gain_src_location_id AND st_move.location_dest_id = inventory.gain_dest_location_id THEN
                    CASE WHEN (barz.purchase_type IS NULL AND barz.distribution_type IS NULL AND barz.storage_type IS NULL) THEN ROUND(COALESCE(st_move.product_uom_qty, 0.0), 2)
                       ELSE COALESCE((st_move.product_uom_qty / barz.factor), 0.0)
                    END
                ELSE 0 END AS gain_quantity,
                CASE WHEN st_move.location_id = inventory.loss_src_location_id AND st_move.location_dest_id = inventory.loss_dest_location_id THEN
                    CASE WHEN (barz.purchase_type IS NULL AND barz.distribution_type IS NULL AND barz.storage_type IS NULL) THEN ROUND(COALESCE(st_move.product_uom_qty, 0.0), 2)
                    ELSE COALESCE((st_move.product_uom_qty / barz.factor), 0.0)
                    END
                ELSE 0 END AS loss_quantity,

                (
                    SELECT array_to_string(array_agg(st.date), ',') AS date
                    FROM
                        stock_inventory st
                    LEFT JOIN stock_warehouse wh ON wh.lot_stock_id = st.location_id
                    WHERE
                        wh.id = inventory.warehouse_id AND
                        st.accounting_date >= '{start_date}'
                        AND st.accounting_date <= '{end_date}'
                        AND st.stock_count_type = 'official'
                        AND st.state in ('done','1st_degree','2nd_degree','no_case')
                        ) AS ticket_date,
                (
                    SELECT
                        COUNT(st.id)
                    FROM
                        stock_inventory st
                    LEFT JOIN stock_warehouse wh ON wh.lot_stock_id = st.location_id
                    WHERE
                         wh.id = inventory.warehouse_id AND
                         st.accounting_date >= '{start_date}'
                        AND st.accounting_date <= '{end_date}'
                        AND st.stock_count_type = 'official'
                        AND st.state in ('done','1st_degree','2nd_degree','no_case')
                ) AS ticket_count,
                pt.name AS product_name,
                st_move.id as move_id,
                st_move.product_uom_qty,
                barz.partner_name,
                inventory.company_id AS company_id
            FROM
                inventory
                LEFT JOIN stock_inventory_line sil ON sil.inventory_id = inventory.st_id
                INNER JOIN product_product product ON product.id = sil.product_id
                INNER JOIN product_template pt ON pt.id = product.product_tmpl_id
                LEFT JOIN stock_move st_move ON st_move.inventory_line_id = sil.id AND st_move.product_id = sil.product_id
                LEFT JOIN stock_quant_move_rel ON stock_quant_move_rel.move_id = st_move.id
                LEFT JOIN stock_quant quant ON quant.id = stock_quant_move_rel.quant_id
                LEFT JOIN inventory_categ_uom_type invent_categ ON invent_categ.uom_categ_id = pt.categ_id
                LEFT JOIN product_category product_category ON product_category.id = invent_categ.parent_categ_id
                LEFT JOIN (
                    SELECT
                    supplierinfo.product_tmpl_id,
                    supplierinfo.is_default,
                    supplierinfo.id AS supplierinfo_id,
                    supplierinfo.name as partner_id,
                    supplier_uom.name,
                    supplierinfo.company_id AS company_id,
                    CASE WHEN supplier_uom.uom_type in ('smaller', 'reference') THEN
                            supplier_uom.factor
                         WHEN supplier_uom.uom_type in ('bigger') THEN
                            1 / supplier_uom.factor
                    END AS factor,
                    supplier.name AS partner_name,
                    supplier_uom.uom_type AS uom_type,
                    CASE WHEN supplier_uom.is_po_default THEN 'purchase'
                       -- ELSE 'standard'
                    END AS purchase_type,
                    CASE WHEN supplier_uom.is_distribution THEN 'distribution'
                       -- ELSE 'standard'
                    END AS distribution_type,
                    CASE WHEN supplier_uom.is_storage THEN 'storage'
                       -- ELSE 'standard'
                    END AS storage_type
                    FROM
                    product_supplierinfo supplierinfo
                    INNER JOIN product_uom supplier_uom ON supplierinfo.id = supplier_uom.vendor_id
                    LEFT JOIN res_partner supplier ON supplierinfo.name = supplier.id
                ) barz ON pt.id = barz.product_tmpl_id AND (
                          barz.purchase_type = invent_categ.uom_type
                          OR storage_type = invent_categ.uom_type
                          OR distribution_type = invent_categ.uom_type)
                          AND CASE
                            WHEN sil.br_supplier_id IS NOT NULL THEN
                                barz.partner_id = sil.br_supplier_id
                            ELSE
                                barz.is_default = True
                            END
                    AND barz.company_id = inventory.company_id
                LEFT JOIN product_uom base_uom ON pt.uom_id = base_uom.id
                LEFT JOIN product_supplierinfo base_supplierinfo ON base_uom.vendor_id = base_supplierinfo.id
                LEFT JOIN res_partner base_supplier ON base_supplierinfo.name = base_supplier.id
            WHERE {sql_product_string}
            GROUP BY
                inventory.warehouse_id, inventory.warehouse_name,
                product_category.name,
                invent_categ.parent_categ_id,
                st_move.location_id,
                inventory.gain_src_location_id,
                st_move.location_dest_id,
                inventory.loss_dest_location_id,
                inventory.gain_dest_location_id,
                inventory.loss_src_location_id,
                barz.factor, pt.name,
                st_move.product_uom_qty,
                barz.partner_name,
                inventory.st_id,
                st_move.id,
                barz.purchase_type,
                barz.distribution_type,
                barz.storage_type,
                inventory.company_id
               -- quant.cost
               -- quant.qty
        """.format(**args)
        self.env.cr.execute(query)
        result = self.env.cr.fetchall()
        self.env.cr.execute("""DELETE FROM inventory_categ_uom_type""")
        return result

    def bind_data(self, ws, report_data, report):
        ws.set_column(0, 16000, 30)
        row = 14
        # ws.write(row, 4, 'Total', self.styles['table_header'])
        ws.merge_range('D15:F15', 'TOTAL', self.styles['table_header'])
        # ws.write(row, 7, 'GAIN', self.styles['table_header'])
        # ws.merge_range('G15:I15', 'GAIN', self.styles['table_header'])

        # ws.write(row, 10, 'LOSS', self.styles['table_header'])
        # ws.merge_range('J15:L15', 'LOSS', self.styles['table_header'])

        perc = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        row += 1
        ws.write(row, 0, 'Warehouse', self.styles['table_header'])
        ws.write(row, 1, '# of Inventory Adjustment', self.styles['table_header'])
        ws.write(row, 2, 'Date of Inventory Adjustment', self.styles['table_header'])
        ws.write(row, 3, 'Total Gain', self.styles['table_header'])
        ws.write(row, 4, 'Total Loss', self.styles['table_header'])
        ws.write(row, 5, 'Net', self.styles['table_header'])

        def _get_sum(row_vals):
            return map(lambda y: sum(y), zip(*map(lambda z: (z[6], z[7], z[4], z[5]), row_vals)))

        categ_columns = {}
        tot_warehouse = {}
        uom_categ = {}

        categ_datas = defaultdict(list)
        categ_datas1 = defaultdict(list)

        col = 6
        warehouse_data1 = {}
        row -= 2
        for data in report_data:
            categ_datas[data[3]].append(data)
            categ_datas1[data[0]].append(data)

        for categ in report.inv_categ_uom_ids:
            uom_categ[categ.uom_categ_id.id] = categ.uom_type

        for key, value in categ_datas.items():
            # row_vals = list(value)
            row_value = value[0]
            if len(value) < 1:
                continue

            # Add in Columns Dict
            categ_columns.update({
                key: {
                    'gain': [col, col + 1],
                    'loss': [col + 2, col + 3],
                    'net': [col + 4, col + 5],
                }
            })

            # Print in Excel (3 rows)
            # 10:6----10:10
            categ_name = row_value[2]
            if row_value[3] and row_value[3] in uom_categ:
                if uom_categ[row_value[3]] == 'purchase':
                    categ_name += ' - (Purchase UoM)'
                elif uom_categ[row_value[3]] == 'standard':
                    categ_name += ' - (Standard)'
                elif uom_categ[row_value[3]] == 'distribution':
                    categ_name += ' - (Distribution)'
                elif uom_categ[row_value[3]] == 'storage':
                    categ_name += ' - (Storage)'
            else:
                if report.uom_type == 'purchase':
                    categ_name += ' - (Purchase UoM)'
                elif report.uom_type == 'standard':
                    categ_name += ' - (Standard)'
                elif report.uom_type == 'distribution':
                    categ_name += ' - (Distribution)'
                elif report.uom_type == 'storage':
                    categ_name += ' - (Storage)'

            ws.merge_range(row, col, row, col + 5, categ_name, self.styles['table_header'])
            # 11:6----11:8
            ws.merge_range(row+1, col, row+1, col+1, 'Gain', self.styles['table_header'])
            # 11:8----11:10
            ws.merge_range(row+1, col+2, row+1, col+3, 'Loss', self.styles['table_header'])

            ws.merge_range(row+1, col+4, row+1, col+5, 'Net', self.styles['table_header'])

            # 12:6----11:10
            ws.write(row+2, col, 'Qty', self.styles['table_header'])
            ws.write(row+2, col+1, 'Amount', self.styles['table_header'])
            ws.write(row+2, col+2, 'Qty', self.styles['table_header'])
            ws.write(row+2, col+3, 'Amount', self.styles['table_header'])
            ws.write(row+2, col+4, 'Net Qty', self.styles['table_header'])
            ws.write(row+2, col+5, 'Net Amount', self.styles['table_header'])

            # Add row
            # gain_quantity, loss_quantity, tot_gain, tot_loss = _get_sum(value)

            # wid = row_value[0]
            # dates = map(lambda a: a[4] and a[4], value)
            # if warehouse_data.get(wid):
            #     warehouse_data[wid]['categs'].update({
            #         key: {
            #             'tot_gain': tot_gain,
            #             'tot_loss': tot_loss,
            #             'gain_quantity': gain_quantity,
            #             'loss_quantity': loss_quantity,
            #         }
            #     })
            # else:
            #     _vals = {}
            #     _vals.update({
            #             'warehouse_name': row_value[1],
            #             'number_st': row_value[8],
            #             'number_date': row_value[7],
            #             'categs': {
            #                 key: {
            #                     'gain_quantity': gain_quantity,
            #                     'loss_quantity': loss_quantity,
            #                     'tot_gain': tot_gain,
            #                     'tot_loss': tot_loss,
            #                     }
            #                 }
            #             })
            #     warehouse_data.update({
            #         wid: _vals
            #     })
            # tot_warehouse.setdefault(wid, {
            #     'gain': 0,
            #     'loss': 0,
            # })
            # tot_warehouse[wid]['gain'] += tot_gain
            # tot_warehouse[wid]['loss'] += tot_loss
            col += 6
        row += 3

        warehouse_data1 = {}
        for key, value in categ_datas1.items():
            tot_warehouse.setdefault(key, {
                'gain': 0,
                'loss': 0,
                'qty_loss': 0,
                'qty_gain': 0,
            })
            for v in value:
                tot_warehouse[key]['gain'] += round(v[4], perc)
                tot_warehouse[key]['loss'] += round(v[5], perc)
                tot_warehouse[key]['qty_loss'] += round(v[7], perc)
                tot_warehouse[key]['qty_gain'] += round(v[6], perc)
                # row_value = value[0]
                if warehouse_data1.get(key):
                    if warehouse_data1[key]['categs'].get(v[3]):
                        warehouse_data1[key]['categs'][v[3]]['tot_gain'] += round(v[4], 2)
                        warehouse_data1[key]['categs'][v[3]]['tot_loss'] += round(v[5], 2)
                        warehouse_data1[key]['categs'][v[3]]['gain_quantity'] += round(v[6], perc)
                        warehouse_data1[key]['categs'][v[3]]['loss_quantity'] += round(v[7], perc)
                        warehouse_data1[key]['categs'][v[3]]['net_quantity'] += round((v[6] - v[7]), perc)
                        warehouse_data1[key]['categs'][v[3]]['net_total'] += round((v[4] - v[5]), 2)
                    else:
                        warehouse_data1[key]['categs'].update({v[3]: {
                            'tot_gain': round(v[4], 2),
                            'tot_loss': round(v[5], 2),
                            'gain_quantity': round(v[6], perc),
                            'loss_quantity': round(v[7], perc),
                            'net_quantity': round((v[6] - v[7]), perc),
                            'net_total': round((v[4] - v[5]), 2)
                        }})
                else:
                    _vals = {}
                    _vals.update({
                            'warehouse_name': v[1],
                            'number_st': v[9],
                            'number_date': v[8],
                            'categs': {
                                v[3]: {
                                    'gain_quantity': round(v[6], perc),
                                    'loss_quantity': round(v[7], perc),
                                    'tot_gain': round(v[4], 2),
                                    'tot_loss': round(v[5], 2),
                                    'net_quantity': round((v[6] - v[7]), perc),
                                    'net_total': round((v[4] - v[5]), 2)
                                    }
                                }
                            })
                    warehouse_data1.update({
                        key: _vals
                    })
        for wid, data in warehouse_data1.iteritems():
            all_category = data.get('categs')
            wh_grand_tot = tot_warehouse.get(wid)
            col = 0
            ws.write(row, col, data['warehouse_name'], self.styles['table_row_left'])
            col += 1
            ws.write(row, col, data['number_st'], self.styles['table_row_left'])
            col += 1
            ws.write(row, col, data['number_date'], self.styles['table_row_left'])

            grand_gain, grand_loss = wh_grand_tot.get('gain'), wh_grand_tot.get('loss')
            col += 1
            ws.write(row, col, grand_gain)
            col += 1
            ws.write(row, col, grand_loss)
            col += 1
            ws.write(row, col, grand_gain - grand_loss)

            for key, by_category in all_category.iteritems():
                # if by_category.get('tot_gain') > 0:
                ws.write(row, categ_columns[key]['gain'][0], by_category.get('gain_quantity'))
                ws.write(row, categ_columns[key]['gain'][1], by_category.get('tot_gain'))
                # if by_category.get('tot_loss') > 0:
                ws.write(row, categ_columns[key]['loss'][0], by_category.get('loss_quantity'))
                ws.write(row, categ_columns[key]['loss'][1], by_category.get('tot_loss'))

                ws.write(row, categ_columns[key]['net'][0], by_category.get('net_quantity'))
                ws.write(row, categ_columns[key]['net'][1], by_category.get('net_total'))
            row += 1

stock_inventory_adj_report('report.stock_inventory_adj.stock_inventory_adj_report', 'stock.inventory.wizard')
