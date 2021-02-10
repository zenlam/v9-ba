# -*- coding: utf-8 -*-

from itertools import groupby
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


class stock_inventory_wizard_damage_first(models.TransientModel):
    _name = 'stock.inventory.wizard.damage.first'

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
                        string='Product Categs',
                        required=True)
    product_ids = fields.Many2many(
                        comodel_name='product.product',
                        string='Product')
    is_lot = fields.Selection([
                ('yes', 'Yes'),
                ('no', 'No')], string='Lot No', default='no')
    report_type = fields.Selection([
                    ('inventory_gl_report', 'Inventory Gain Loss Report'),
                    ('inventory_damage_report', 'Inventory Damage Report')
                    ], string='Report Type')
    inv_categ_uom_ids = fields.One2many('stock.inventory.categ.uom.damage.first', 'inv_first_wizard_id', string='Categires UoM')
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
        return self.env['report'].get_action(self, 'stock_inventory_adj.stock_inventory_adj_damage_report_first')

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

class stock_inventory_categ_uom_damage_first(models.TransientModel):
    _name = 'stock.inventory.categ.uom.damage.first'

    uom_categ_id = fields.Many2one('product.category', string='Category')
    uom_type = fields.Selection([
                    ('standard', 'Standard'),
                    ('purchase', 'Purchase UoM'),
                    ('distribution', 'Distribution'),
                    ('storage', 'Storage'),
                    ], string='UoM Type')
    inv_first_wizard_id = fields.Many2one('stock.inventory.wizard.damage.first', string='Wizard')


class stock_inventory_adj_damage_report_first(ReportXlsx):
    _name = 'report.stock_inventory_adj.stock_inventory_adj_damage_report_first'

    def generate_xlsx_report(self, wb, data, report):
        Product = self.env['product.product']
        ProductCateg = self.env['product.category']
        StockInventoryUomCateg = self.env['stock.inventory.categ.uom.damage.first']

        ws = wb.add_worksheet('Inventory Damage First Report')
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

        for cat in product_categs:
            child_categ_ids = ProductCateg.search([('id', 'child_of', cat.id)])
            if not report.inv_categ_uom_ids:
                for child_categ in child_categ_ids:
                    self.env.cr.execute("""
                        INSERT INTO inventory_categ_uom_type (uom_categ_id, uom_type, parent_categ_id)
                            values(%s, %s, %s)""", (child_categ.id, report.uom_type, cat.id))
            else:
                if report.inv_categ_uom_ids and len(report.inv_categ_uom_ids) == 1 and not report.inv_categ_uom_ids.uom_categ_id:
                    uom_type = report.inv_categ_uom_ids.uom_type
                    for child_categ in child_categ_ids:
                        self.env.cr.execute("""
                            INSERT INTO inventory_categ_uom_type (uom_categ_id, uom_type, parent_categ_id)
                                values(%s, %s, %s)""", (child_categ.id, uom_type, cat.id))
                else:
                    if report.inv_categ_uom_ids:
                        line = StockInventoryUomCateg.search([
                            ('inv_first_wizard_id', '=', report.id),
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
            'sql_product_string': sql_product_string,
            'lot_number': report.is_lot,
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
        ws.write('B1', u'Inventory Damage Detail - 1 Report', self.styles['bold'])

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

        ws.write('A8', u'Lot Number', self.styles['bold'])
        lot = 'NO'
        if report.is_lot:
            lot = 'Yes'
        ws.write('B8', lot)

    def get_domain(self, report):
        return {}

    def get_data(self, args):
        if args.get('lot_number') == 'yes':
            query = """
                WITH warehouse AS (
                    SELECT
                        warehouse.id AS warehouse_id,
                        warehouse.name AS warehouse_name,
                        warehouse.damage_src_location_id AS damage_src_location_id,
                        warehouse.damage_dest_location_id AS damage_dest_location_id,
                        warehouse.company_id AS company_id
                    FROM
                        stock_warehouse warehouse
                    WHERE
                        warehouse.company_id = {company_id}
                        AND {sql_warehouse_string}
                    GROUP BY warehouse.id
                )
                SELECT
                    warehouse.warehouse_id AS warehouse_id,
                    warehouse.warehouse_name AS warehouse_name,
                    ROUND(CAST((CASE WHEN st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id THEN SUM(COALESCE((quant.cost * quant.qty), 0.0))
                        ELSE 0.0
                    END ) AS NUMERIC), 2) AS damage_cost,
                    CASE WHEN st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id THEN
                        CASE WHEN (barz.purchase_type IS NULL AND barz.distribution_type IS NULL AND barz.storage_type IS NULL) THEN SUM(COALESCE(quant.qty, 0.0))
                           ELSE COALESCE((quant.qty / barz.factor), 0.0)
                        END
                    ELSE 0 END AS damage_quantity,
                    pt.name AS product_name,
                    barz.partner_name,
                    product.id AS product_id,
                    barz.factor,
                    spl.id AS lot_id,
                    spl.name as lot_name,
                    quant.qty
                FROM
                    warehouse
                    LEFT JOIN stock_move st_move ON st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id
                    INNER JOIN product_product product ON product.id = st_move.product_id
                    INNER JOIN product_template pt ON pt.id = product.product_tmpl_id
                    LEFT JOIN stock_quant_move_rel ON stock_quant_move_rel.move_id = st_move.id
                    LEFT JOIN stock_quant quant ON quant.id = stock_quant_move_rel.quant_id
                    LEFT JOIN stock_production_lot spl ON spl.id = st_move.restrict_lot_id
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
                            END AS purchase_type,
                            CASE WHEN supplier_uom.is_distribution THEN 'distribution'
                            END AS distribution_type,
                            CASE WHEN supplier_uom.is_storage THEN 'storage'
                            END AS storage_type
                            FROM
                            product_supplierinfo supplierinfo
                            INNER JOIN product_uom supplier_uom ON supplierinfo.id = supplier_uom.vendor_id
                            LEFT JOIN res_partner supplier ON supplierinfo.name = supplier.id
                        ) barz ON pt.id = barz.product_tmpl_id AND (
                          barz.purchase_type = invent_categ.uom_type
                          OR storage_type = invent_categ.uom_type
                          OR distribution_type = invent_categ.uom_type)
                          AND CASE WHEN st_move.vendor_id IS NOT NULL THEN
                                barz.partner_id = st_move.vendor_id
                            ELSE
                                barz.is_default = True
                        END AND barz.company_id = warehouse.company_id
                    LEFT JOIN product_uom base_uom ON pt.uom_id = base_uom.id
                    LEFT JOIN product_supplierinfo base_supplierinfo ON base_uom.vendor_id = base_supplierinfo.id
                    LEFT JOIN res_partner base_supplier ON base_supplierinfo.name = base_supplier.id
                    WHERE {sql_product_string} AND st_move.date >= '{start_date}' AND st_move.date <= '{end_date}' AND st_move.state = 'done'
                    AND quant.qty >= 0
                GROUP BY
                    warehouse.warehouse_id,
                    warehouse.warehouse_name,
                    product_category.name,
                    invent_categ.parent_categ_id,
                    st_move.location_id,
                    warehouse.damage_src_location_id,
                    st_move.location_dest_id,
                    warehouse.damage_dest_location_id,
                    barz.factor,
                    pt.name,
                    quant.qty,
                    barz.partner_name,
                    product.id,
                    spl.id,
                    spl.name,
                    barz.purchase_type,
                    barz.distribution_type,
                    barz.storage_type,
                    st_move.id,
                    quant.id,
                    warehouse.company_id
        """.format(**args)
        else:
            query = """
                WITH warehouse AS (
                    SELECT
                        warehouse.id AS warehouse_id,
                        warehouse.name AS warehouse_name,
                        warehouse.damage_src_location_id AS damage_src_location_id,
                        warehouse.damage_dest_location_id AS damage_dest_location_id,
                        warehouse.company_id AS company_id
                    FROM
                        stock_warehouse warehouse
                    WHERE
                        warehouse.company_id = {company_id}
                        AND {sql_warehouse_string}
                    GROUP BY warehouse.id
                    )
                    SELECT
                        warehouse.warehouse_id AS warehouse_id,
                        warehouse.warehouse_name AS warehouse_name,
                        ROUND(CAST((CASE WHEN st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id THEN SUM(COALESCE((quant.cost * quant.qty), 0.0))
                            ELSE 0.0
                        END ) AS NUMERIC), 2) AS damage_cost,
                        CASE WHEN st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id THEN
                            CASE WHEN (barz.purchase_type IS NULL AND barz.distribution_type IS NULL AND barz.storage_type IS NULL) THEN SUM(COALESCE(quant.qty, 0.0))
                            ELSE COALESCE((quant.qty / barz.factor), 0.0)
                            END
                        ELSE 0 END AS damage_quantity,
                        pt.name AS product_name,
                        barz.partner_name,
                        product.id AS product_id,
                        st_move.id as move_id,
                        warehouse.company_id AS company_id,
                        warehouse.damage_src_location_id AS damage_src_location_id,
                        warehouse.damage_dest_location_id AS loss_dest_location_id,
                        quant.qty
                    FROM
                        warehouse
                        LEFT JOIN stock_move st_move ON st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id
                        INNER JOIN product_product product ON product.id = st_move.product_id
                        INNER JOIN product_template pt ON pt.id = product.product_tmpl_id
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
                                END AS purchase_type,
                                CASE WHEN supplier_uom.is_distribution THEN 'distribution'
                                END AS distribution_type,
                                CASE WHEN supplier_uom.is_storage THEN 'storage'
                                END AS storage_type
                            FROM
                                product_supplierinfo supplierinfo
                                INNER JOIN product_uom supplier_uom ON supplierinfo.id = supplier_uom.vendor_id
                                LEFT JOIN res_partner supplier ON supplierinfo.name = supplier.id
                        ) barz ON pt.id = barz.product_tmpl_id AND (
                          barz.purchase_type = invent_categ.uom_type
                          OR storage_type = invent_categ.uom_type
                          OR distribution_type = invent_categ.uom_type)
                          AND CASE WHEN st_move.vendor_id IS NOT NULL THEN
                                barz.partner_id = st_move.vendor_id
                            ELSE
                                barz.is_default = True
                            END AND barz.company_id = warehouse.company_id
                        LEFT JOIN product_uom base_uom ON pt.uom_id = base_uom.id
                        LEFT JOIN product_supplierinfo base_supplierinfo ON base_uom.vendor_id = base_supplierinfo.id
                        LEFT JOIN res_partner base_supplier ON base_supplierinfo.name = base_supplier.id
                    WHERE {sql_product_string} AND st_move.date >= '{start_date}' AND st_move.date <= '{end_date}' AND st_move.state = 'done'
                    AND quant.qty >= 0
                    GROUP BY
                        warehouse.warehouse_id,
                        warehouse.warehouse_name,
                        product_category.name,
                        invent_categ.parent_categ_id,
                        st_move.location_id,
                        warehouse.damage_src_location_id,
                        st_move.location_dest_id,
                        warehouse.damage_dest_location_id,
                        barz.factor,
                        pt.name,
                        quant.qty,
                        barz.partner_name,
                        st_move.id,
                        quant.id,
                        product.id,
                        warehouse.company_id,
                        barz.purchase_type,
                        barz.distribution_type,
                        barz.storage_type
            """.format(**args)
        self.env.cr.execute(query)
        result = self.env.cr.fetchall()
        self.env.cr.execute("""DELETE FROM inventory_categ_uom_type""")
        return result

    def bind_data(self, ws, report_data, report):
        ws.set_column(0, 20, 30)
        row = 10
        # ws.merge_range('D15:F15', 'TOTAL', self.styles['table_header'])

        ws.write(row, 0, 'Warehouse', self.styles['table_header'])
        ws.write(row, 1, 'Product', self.styles['table_header'])
        ws.write(row, 2, 'Lot number', self.styles['table_header'])
        ws.write(row, 3, 'Damage(QTY)', self.styles['table_header'])
        ws.write(row, 4, 'Damage(RM)', self.styles['table_header'])

        perc = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        col = 6
        warehouse_data = {}
        grouped = groupby(report_data, key=lambda x: x[0])
        if report.is_lot == 'no':
            for key, val in grouped:
                for l in list(val):
                    if warehouse_data.get(key):
                        if warehouse_data[key]['products'].get(l[6]):
                            warehouse_data[key]['products'][l[6]]['tot_damage'] += round(l[2], 2)
                            warehouse_data[key]['products'][l[6]]['damage_quantity'] += round(l[3], perc)
                        else:
                            warehouse_data[key]['products'].update({
                                 l[6]: {
                                    'product_name': l[4],
                                    'tot_damage': round(l[2], 2),
                                    'damage_quantity': round(l[3], perc),
                                 }})
                    else:
                        _vals = {}
                        _vals.update({
                                'warehouse_name': l[1],
                                'products': {
                                    l[6]: {
                                        'product_name': l[4],
                                        'tot_damage': round(l[2], 2),
                                        'damage_quantity': round(l[3], perc),
                                        }
                                    }
                                })
                        warehouse_data.update({
                            key: _vals
                        })
            row += 1
            for wid, data in warehouse_data.iteritems():
                warehouse_name = data['warehouse_name']
                all_products = data.get('products')
                for key, product in all_products.iteritems():
                    col = 0
                    ws.write(row, col, warehouse_name, self.styles['table_row_left'])
                    col += 1
                    ws.write(row, col, product['product_name'], self.styles['table_row_left'])
                    col += 1
                    ws.write(row, col, '', self.styles['table_row_left'])
                    col += 1
                    ws.write(row, col, product['damage_quantity'], self.styles['table_row_right'])
                    col += 1
                    ws.write(row, col, product['tot_damage'], self.styles['table_row_right'])
                    row += 1
        else:
            for key, val in grouped:
                for l in list(val):
                    if warehouse_data.get(key):
                        if warehouse_data[key].get(l[6]):
                            if warehouse_data[key][l[6]]['lots'].get(l[9]):
                                warehouse_data[key][l[6]]['lots'][l[9]]['tot_damage'] += round(l[2], 2)
                                warehouse_data[key][l[6]]['lots'][l[9]]['damage_quantity'] += round(l[3], perc)
                            else:
                                warehouse_data[key][l[6]]['lots'].update({
                                    l[9]: {
                                        'warehouse_name': l[1],
                                        'product_name': l[4],
                                        'damage_quantity': round(l[3], perc),
                                        'tot_damage': round(l[2], 2),
                                        'lot_name': l[9],
                                    }
                                })
                        else:
                            warehouse_data[key].update({
                                 l[6]: {
                                        'lots': {
                                            l[9]: {
                                                'warehouse_name': l[1],
                                                'product_name': l[4],
                                                'tot_damage': round(l[2], 2),
                                                'damage_quantity': round(l[3], perc),
                                                'lot_name': l[9],
                                            }
                                        }
                                    }
                                })
                    else:
                        _vals = {}
                        _vals.update({
                                l[6]: {
                                    'product_name': l[4],
                                    'lots': {
                                        l[9]: {
                                            'warehouse_name': l[1],
                                            'tot_damage': round(l[2], 2),
                                            'damage_quantity': round(l[3], perc),
                                            'product_name': l[4],
                                            'lot_name': l[9],
                                        }
                                    }
                                }
                        })
                        warehouse_data.update({
                            key: _vals
                        })

            row += 1
            for wid, data in warehouse_data.iteritems():
                for key, product in data.iteritems():
                    lot_data = product.get('lots')
                    for lot_key, lot_data in lot_data.iteritems():
                        col = 0
                        ws.write(row, col, lot_data['warehouse_name'], self.styles['table_row_left'])
                        col += 1
                        ws.write(row, col, lot_data['product_name'], self.styles['table_row_left'])
                        col += 1
                        ws.write(row, col, lot_data['lot_name'], self.styles['table_row_left'])
                        col += 1
                        ws.write(row, col, lot_data['damage_quantity'], self.styles['table_row_right'])
                        col += 1
                        ws.write(row, col, lot_data['tot_damage'], self.styles['table_row_right'])
                        col += 1
                        row += 1

stock_inventory_adj_damage_report_first('report.stock_inventory_adj.stock_inventory_adj_damage_report_first', 'stock.inventory.wizard.damage.first')
