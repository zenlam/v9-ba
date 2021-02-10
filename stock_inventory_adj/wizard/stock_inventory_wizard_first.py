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


class stock_inventory_wizard_first(models.TransientModel):
    _name = 'stock.inventory.wizard.first'

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
    inv_categ_uom_ids = fields.One2many('stock.inventory.categ.uom.first', 'inv_first_wizard_id', string='Categires UoM')
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
        return self.env['report'].get_action(self, 'stock_inventory_adj.stock_inventory_adj_report_first')

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


class stock_inventory_categ_uom_first(models.TransientModel):
    _name = 'stock.inventory.categ.uom.first'

    uom_categ_id = fields.Many2one('product.category', string='Category')
    uom_type = fields.Selection([
                    ('standard', 'Standard'),
                    ('purchase', 'Purchase UoM'),
                    ('distribution', 'Distribution'),
                    ('storage', 'Storage'),
                    ], string='UoM Type')
    inv_first_wizard_id = fields.Many2one('stock.inventory.wizard.first', string='Wizard')


class stock_inventory_adj_report_first(ReportXlsx):
    _name = 'report.stock_inventory_adj.stock_inventory_adj_report_first'

    def generate_xlsx_report(self, wb, data, report):
        Product = self.env['product.product']
        ProductCateg = self.env['product.category']
        StockInventoryUomCateg = self.env['stock.inventory.categ.uom.first']

        ws = wb.add_worksheet('Inventory Details One Report')
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
        ws.write('B1', u'Inventory Adjustment Detail - 1', self.styles['bold'])

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
        ws.write('B8', report.report_type or '')

        ws.write('A9', u'Lot No', self.styles['bold'])
        lot_no = 'NO'
        if report.is_lot == 'yes':
            lot_no = 'Yes'
        ws.write('B9', lot_no)

    def get_domain(self, report):
        return {}

    def get_data(self, args):
        if args.get('lot_number') == 'yes':
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
                            AND st.state in ('done', '1st_degree', '2nd_degree', 'no_case')
                            AND {sql_warehouse_string}
                        GROUP BY warehouse.id, st.location_id, st.id
                )
                SELECT
                    inventory.warehouse_id AS warehouse_id,
                    inventory.warehouse_name AS warehouse_name,
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
                    pt.name AS product_name,
                    barz.partner_name,
                    st_move.product_uom_qty,
                    product.id AS product_id,
                    sil.theoretical_qty AS theoretical_qty,
                    sil.product_qty AS real_qty,
                    barz.factor,
                    spl.id AS lot_id,
                    spl.name as lot_name,
                    inventory.company_id AS company_id
                FROM
                    inventory
                    LEFT JOIN stock_inventory_line sil ON sil.inventory_id = inventory.st_id
                    INNER JOIN product_product product ON product.id = sil.product_id
                    INNER JOIN product_template pt ON pt.id = product.product_tmpl_id
                    LEFT JOIN stock_production_lot spl ON spl.id = sil.prod_lot_id
                    LEFT JOIN stock_move st_move
                        ON ((st_move.inventory_line_id = sil.id AND st_move.product_id = sil.product_id AND st_move.restrict_lot_id = spl.id)
                        OR (st_move.inventory_line_id = sil.id AND st_move.product_id = sil.product_id AND st_move.restrict_lot_id IS NULL))
                    LEFT JOIN stock_quant_move_rel ON stock_quant_move_rel.move_id = st_move.id
                    LEFT JOIN stock_quant quant ON quant.id = stock_quant_move_rel.quant_id
                    LEFT JOIN inventory_categ_uom_type invent_categ ON invent_categ.uom_categ_id = pt.categ_id
                    LEFT JOIN product_category product_category ON product_category.id = invent_categ.parent_categ_id
                    LEFT JOIN (
                        SELECT
                        supplierinfo.product_tmpl_id,
                        supplierinfo.id AS supplierinfo_id,
                        supplierinfo.name as partner_id,
                        supplierinfo.is_default,
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
                        OR distribution_type = invent_categ.uom_type
                    )  AND CASE
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
                    inventory.warehouse_id,
                    inventory.warehouse_name,
                    product_category.name,
                    invent_categ.parent_categ_id, st_move.location_id, inventory.gain_src_location_id,
                    st_move.location_dest_id, inventory.loss_dest_location_id, inventory.gain_dest_location_id,
                    inventory.loss_src_location_id,
                    barz.factor,
                    pt.name,
                    st_move.product_uom_qty,
                    barz.partner_name,
                    product.id,
                    sil.theoretical_qty,
                    sil.product_qty,
                    st_move.id,
                    spl.id,
                    spl.name,
                    barz.purchase_type,
                    barz.distribution_type,
                    barz.storage_type,
                    inventory.company_id
        """.format(**args)
        else:
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
                        AND st.state in ('done', '1st_degree', '2nd_degree', 'no_case')
                        AND {sql_warehouse_string}
                    GROUP BY warehouse.id, st.location_id, st_id
                    )
                    SELECT
                        inventory.warehouse_id AS warehouse_id,
                        inventory.warehouse_name AS warehouse_name,
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
                        pt.name AS product_name,
                        barz.partner_name,
                        st_move.product_uom_qty,
                        product.id AS product_id,
                        sil.theoretical_qty AS theoretical_qty,
                        sil.product_qty AS real_qty,
                        st_move.id as move_id,
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
                            supplierinfo.id AS supplierinfo_id,
                            supplierinfo.name as partner_id,
                            supplier_uom.name,
                            supplierinfo.is_default,
                            supplierinfo.company_id AS company_id,
                            CASE WHEN supplier_uom.uom_type in ('smaller', 'reference') THEN
                                    supplier_uom.factor
                                WHEN supplier_uom.uom_type in ('bigger') THEN
                                    1 / supplier_uom.factor
                            END AS factor,
                            supplier.name AS partner_name,
                            supplier_uom.uom_type AS uom_type,
                            CASE WHEN supplier_uom.is_po_default THEN 'purchase'
                             --   ELSE 'standard'
                            END AS purchase_type,
                            CASE WHEN supplier_uom.is_distribution THEN 'distribution'
                              --  ELSE 'standard'
                            END AS distribution_type,
                            CASE WHEN supplier_uom.is_storage THEN 'storage'
                              --  ELSE 'standard'
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
                        inventory.warehouse_id,
                        inventory.warehouse_name,
                        product_category.name,
                        invent_categ.parent_categ_id, st_move.location_id, inventory.gain_src_location_id,
                        st_move.location_dest_id, inventory.loss_dest_location_id, inventory.gain_dest_location_id,
                        inventory.loss_src_location_id,
                        barz.factor,
                        pt.name,
                        st_move.product_uom_qty,
                        barz.partner_name,
                        product.id, sil.theoretical_qty,
                        sil.product_qty,
                        st_move.id,
                        barz.purchase_type,
                        barz.distribution_type,
                        barz.storage_type,
                        inventory.company_id
            """.format(**args)
        self.env.cr.execute(query)
        result = self.env.cr.fetchall()
        self.env.cr.execute("""DELETE FROM inventory_categ_uom_type""")
        return result

    def bind_data(self, ws, report_data, report):
        ws.set_column(0, 20, 30)
        row = 10
        # ws.merge_range('D15:F15', 'TOTAL', self.styles['table_header'])

        perc = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        ws.write(row, 0, 'Warehouse', self.styles['table_header'])
        ws.write(row, 1, 'Product', self.styles['table_header'])

        if report.is_lot == 'yes':
            ws.write(row, 2, 'Lot number', self.styles['table_header'])
            ws.write(row, 3, 'Theoretical Balance', self.styles['table_header'])
            ws.write(row, 4, 'Actual Balance', self.styles['table_header'])
            ws.write(row, 5, 'Gain(QTY)', self.styles['table_header'])
            ws.write(row, 6, 'Loss(QTY)', self.styles['table_header'])
            ws.write(row, 7, 'Net(QTY)', self.styles['table_header'])

            ws.write(row, 8, 'Gain(RM)', self.styles['table_header'])
            ws.write(row, 9, 'Loss(RM)', self.styles['table_header'])
            ws.write(row, 10, 'Net(RM)', self.styles['table_header'])
        else:
            ws.write(row, 2, 'Theoretical Balance', self.styles['table_header'])
            ws.write(row, 3, 'Actual Balance', self.styles['table_header'])
            ws.write(row, 4, 'Gain(QTY)', self.styles['table_header'])
            ws.write(row, 5, 'Loss(QTY)', self.styles['table_header'])
            ws.write(row, 6, 'Net(QTY)', self.styles['table_header'])

            ws.write(row, 7, 'Gain(RM)', self.styles['table_header'])
            ws.write(row, 8, 'Loss(RM)', self.styles['table_header'])
            ws.write(row, 9, 'Net(RM)', self.styles['table_header'])

        # def _get_sum(row_vals):
        #     return map(lambda y: sum(y), zip(*map(lambda z: (z[6], z[7], z[4], z[5]), row_vals)))

        final_gain_quantity = 0.0
        final_loss_quantity = 0.0
        final_net_quantity = 0.0
        final_theoretical_qty = 0.0
        final_real_qty = 0.0
        final_tot_gain = 0.0
        final_tot_loss = 0.0
        final_tot_net = 0.0

        col = 6
        warehouse_data = {}
        grouped = groupby(report_data, key=lambda x: x[0])
        if report.is_lot == 'no':
            for key, val in grouped:
                for l in list(val):
                    if warehouse_data.get(key):
                        if warehouse_data[key]['products'].get(l[9]):
                            warehouse_data[key]['products'][l[9]]['tot_gain'] += round(l[2], 2)
                            warehouse_data[key]['products'][l[9]]['tot_loss'] += round(l[3], 2)
                            warehouse_data[key]['products'][l[9]]['gain_quantity'] += round(l[4], perc)
                            warehouse_data[key]['products'][l[9]]['loss_quantity'] += round(l[5], perc)
                            warehouse_data[key]['products'][l[9]]['theoretical_qty'] += round(l[10], perc)
                            warehouse_data[key]['products'][l[9]]['real_qty'] += round(l[11], perc)
                        else:
                            warehouse_data[key]['products'].update({
                                 l[9]: {
                                    'product_name': l[6],
                                    'tot_gain': round(l[2], 2),
                                    'tot_loss': round(l[3], 2),
                                    'gain_quantity': round(l[4], perc),
                                    'loss_quantity': round(l[5], perc),
                                    'theoretical_qty': round(l[10], perc),
                                    'real_qty': round(l[11], perc),
                                 }})
                    else:
                        _vals = {}
                        _vals.update({
                                'warehouse_name': l[1],
                                'products': {
                                    l[9]: {
                                        'product_name': l[6],
                                        'gain_quantity': round(l[4], perc),
                                        'loss_quantity': round(l[5], perc),
                                        'tot_gain': round(l[2], 2),
                                        'tot_loss': round(l[3], 2),
                                        'theoretical_qty': round(l[10], perc),
                                        'real_qty': round(l[11], perc),
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
                    if product['theoretical_qty'] == 0.0 and product['real_qty'] == 0.0 and product['gain_quantity'] == 0.0 and \
                            product['loss_quantity'] == 0.0 and product['tot_gain'] == 0.0 and product['tot_loss'] == 0.0:
                            continue
                    col = 0
                    ws.write(row, col, warehouse_name, self.styles['table_row_left'])
                    col += 1
                    ws.write(row, col, product['product_name'], self.styles['table_row_left'])
                    # col += 1
                    # ws.write(row, col, '', self.styles['table_row_left'])
                    col += 1
                    final_theoretical_qty += product['theoretical_qty']
                    ws.write(row, col, product['theoretical_qty'], self.styles['table_row_left'])
                    col += 1
                    final_real_qty += product['real_qty']
                    ws.write(row, col, product['real_qty'], self.styles['table_row_left'])
                    col += 1
                    final_gain_quantity += product['gain_quantity']
                    ws.write(row, col, product['gain_quantity'], self.styles['table_row_left'])
                    col += 1
                    final_loss_quantity += product['loss_quantity']
                    ws.write(row, col, product['loss_quantity'], self.styles['table_row_left'])
                    col += 1
                    final_net_quantity += (product['gain_quantity'] - product['loss_quantity'])
                    ws.write(row, col, (product['gain_quantity'] - product['loss_quantity']), self.styles['table_row_left'])
                    col += 1
                    final_tot_gain += product['tot_gain']
                    ws.write(row, col, product['tot_gain'], self.styles['table_row_left'])
                    col += 1
                    final_tot_loss += product['tot_loss']
                    ws.write(row, col, product['tot_loss'], self.styles['table_row_left'])
                    col += 1
                    final_tot_net += (product['tot_gain'] - product['tot_loss'])
                    ws.write(row, col, (product['tot_gain'] - product['tot_loss']), self.styles['table_row_left'])
                    row += 1

            col = 0
            ws.write(row, col, 'Grand Total', self.styles['table_header'])
            col += 1
            ws.write(row, col, '', self.styles['table_header'])
            col += 1
            ws.write(row, col, final_theoretical_qty, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_real_qty, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_gain_quantity, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_loss_quantity, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_net_quantity, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_tot_gain, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_tot_loss, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_tot_net, self.styles['table_header'])
        else:
            for key, val in grouped:
                for l in list(val):
                    if warehouse_data.get(key):
                        if warehouse_data[key].get(l[9]):
                            if warehouse_data[key][l[9]]['lots'].get(l[14]):
                                warehouse_data[key][l[9]]['lots'][l[14]]['tot_gain'] += round(l[2], 2)
                                warehouse_data[key][l[9]]['lots'][l[14]]['tot_loss'] += round(l[3], 2)
                                warehouse_data[key][l[9]]['lots'][l[14]]['gain_quantity'] += round(l[4], perc)
                                warehouse_data[key][l[9]]['lots'][l[14]]['loss_quantity'] += round(l[5], perc)
                                warehouse_data[key][l[9]]['lots'][l[14]]['theoretical_qty'] += round(l[10], perc)
                                warehouse_data[key][l[9]]['lots'][l[14]]['real_qty'] += round(l[11], perc)
                            else:
                                warehouse_data[key][l[9]]['lots'].update({
                                    l[14]: {
                                        'product_name': l[6],
                                        'gain_quantity': round(l[4], perc),
                                        'loss_quantity': round(l[5], perc),
                                        'tot_gain': round(l[2], 2),
                                        'tot_loss': round(l[3], 2),
                                        'theoretical_qty': round(l[10], perc),
                                        'real_qty': round(l[11], perc),
                                        'lot_name': l[14],
                                        'warehouse_name': l[1],
                                    }
                                })
                        else:
                            warehouse_data[key].update({
                                 l[9]: {
                                        'lots': {
                                            l[14]: {
                                                'product_name': l[6],
                                                'gain_quantity': round(l[4], perc),
                                                'loss_quantity': round(l[5], perc),
                                                'tot_gain': round(l[2], 2),
                                                'tot_loss': round(l[3], 2),
                                                'theoretical_qty': round(l[10], perc),
                                                'real_qty': round(l[11], perc),
                                                'lot_name': l[14],
                                                'warehouse_name': l[1],
                                            }
                                        }
                                    }
                                })
                    else:
                        _vals = {}
                        _vals.update({
                                l[9]: {
                                    'product_name': l[6],
                                    'lots': {
                                        l[14]: {
                                            'product_name': l[6],
                                            'gain_quantity': round(l[4], perc),
                                            'loss_quantity': round(l[5], perc),
                                            'tot_gain': round(l[2], 2),
                                            'tot_loss': round(l[3], 2),
                                            'theoretical_qty': round(l[10], perc),
                                            'real_qty': round(l[11], perc),
                                            'lot_name': l[14],
                                            'warehouse_name': l[1],
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
                        if lot_data['theoretical_qty'] == 0.0 and lot_data['real_qty'] == 0.0 and lot_data['gain_quantity'] == 0.0 and \
                                lot_data['loss_quantity'] == 0.0 and lot_data['tot_gain'] == 0.0 and lot_data['tot_loss'] == 0.0:
                            continue
                        col = 0
                        ws.write(row, col, lot_data['warehouse_name'], self.styles['table_row_left'])
                        col += 1
                        ws.write(row, col, lot_data['product_name'], self.styles['table_row_left'])
                        col += 1
                        ws.write(row, col, lot_data['lot_name'], self.styles['table_row_left'])
                        col += 1
                        final_theoretical_qty += lot_data['theoretical_qty']
                        ws.write(row, col, lot_data['theoretical_qty'], self.styles['table_row_left'])
                        col += 1
                        final_real_qty += lot_data['real_qty']
                        ws.write(row, col, lot_data['real_qty'], self.styles['table_row_left'])
                        col += 1
                        final_gain_quantity += lot_data['gain_quantity']
                        ws.write(row, col, lot_data['gain_quantity'], self.styles['table_row_left'])
                        col += 1
                        final_loss_quantity += lot_data['loss_quantity']
                        ws.write(row, col, lot_data['loss_quantity'], self.styles['table_row_left'])
                        col += 1
                        final_net_quantity += (lot_data['gain_quantity'] - lot_data['loss_quantity'])
                        ws.write(row, col, (lot_data['gain_quantity'] - lot_data['loss_quantity']), self.styles['table_row_left'])
                        col += 1
                        final_tot_gain += lot_data['tot_gain']
                        ws.write(row, col, lot_data['tot_gain'], self.styles['table_row_left'])
                        col += 1
                        final_tot_loss += lot_data['tot_loss']
                        ws.write(row, col, lot_data['tot_loss'], self.styles['table_row_left'])
                        col += 1
                        final_tot_net += (lot_data['tot_gain'] - lot_data['tot_loss'])
                        ws.write(row, col, (lot_data['tot_gain'] - lot_data['tot_loss']), self.styles['table_row_left'])
                        row += 1

            col = 0
            ws.write(row, col, 'Grand Total', self.styles['table_header'])
            col += 1
            ws.write(row, col, '', self.styles['table_header'])
            col += 1
            ws.write(row, col, '', self.styles['table_header'])
            col += 1
            ws.write(row, col, final_theoretical_qty, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_real_qty, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_gain_quantity, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_loss_quantity, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_net_quantity, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_tot_gain, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_tot_loss, self.styles['table_header'])
            col += 1
            ws.write(row, col, final_tot_net, self.styles['table_header'])

stock_inventory_adj_report_first('report.stock_inventory_adj.stock_inventory_adj_report_first', 'stock.inventory.wizard.first')
