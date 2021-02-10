# -*- coding: utf-8 -*-

from collections import defaultdict
import pytz

from openerp import api, fields, models
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError


import time


DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def convert_timezone(from_tz, to_tz, dt):
    from_tz = pytz.timezone(from_tz).localize(datetime.strptime(dt, DATETIME_FORMAT))
    to_tz = from_tz.astimezone(pytz.timezone(to_tz))
    return to_tz.strftime(DATETIME_FORMAT)


class stock_inventory_damage_wizard(models.TransientModel):
    _name = 'stock.inventory.damage.wizard'

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
                ('no', 'No')], string='Lot No', default='no')
    report_type = fields.Selection([
                    ('inventory_gl_report', 'Inventory Gain Loss Report'),
                    ('inventory_damage_report', 'Inventory Damage Report')
                    ], string='Report Type')
    inv_categ_uom_ids = fields.One2many('stock.inventory.categ.uom.damage', 'inv_wizard_id', string='Categires UoM')
    uom_type = fields.Selection([
                    ('standard', 'Standard'),
                    ('purchase', 'Purchase UoM'),
                    ('distribution', 'Distribution'),
                    ('storage', 'Storage'),
                    ], string='UoM Type', required=True, default='standard')

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
        return self.env['report'].get_action(self, 'stock_inventory_adj.stock_inventory_adj_damage_report')

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


class stock_inventory_categ_uom_damage(models.TransientModel):
    _name = 'stock.inventory.categ.uom.damage'

    uom_categ_id = fields.Many2one('product.category', string='Category')
    uom_type = fields.Selection([
                    ('standard', 'Standard'),
                    ('purchase', 'Purchase UoM'),
                    ('distribution', 'Distribution'),
                    ('storage', 'Storage'),
                    ], string='UoM Type')
    inv_wizard_id = fields.Many2one('stock.inventory.damage.wizard', string='Wizard')


class stock_inventory_adj_damage_report(ReportXlsx):
    _name = 'report.stock_inventory_adj.stock_inventory_adj_damage_report'

    def generate_xlsx_report(self, wb, data, report):
        Product = self.env['product.product']
        ProductCateg = self.env['product.category']
        StockInventoryUomCateg = self.env['stock.inventory.categ.uom.damage']

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
        move_product_string = '1=1'
        if product_ids:
            sql_product_string = 'product.id in ' + str(product_ids).replace('[', '(').replace(']', ')')
            move_product_string = 'st_move.product_id in ' + str(product_ids).replace('[', '(').replace(']', ')')

        sql_warehouse_string = '1=1'
        if warehouse_ids:
            sql_warehouse_string = 'warehouse.id in ' + str(warehouse_ids).replace('[', '(').replace(']', ')')

        credentials = {
            'start_date': start_date,
            'end_date': end_date,
            'company_id': self.env.user.company_id.id,
            'sql_warehouse_string': sql_warehouse_string,
            'sql_product_string': sql_product_string,
            'move_product_string': move_product_string,
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
        ws.write('B1', u'Inventory Damage Summary', self.styles['bold'])

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

        # ws.write('A8', u'Report Type', self.styles['bold'])
        # ws.write('B8', report.report_type)

    def get_domain(self, report):
        return {}

    def get_data(self, args):
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
                product_category.name AS categ_name,
                invent_categ.parent_categ_id AS parent_categ_id,
                ROUND(CAST((CASE WHEN st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id THEN SUM(COALESCE((quant.cost * quant.qty), 0.0))
                    ELSE 0.0
                END ) AS NUMERIC), 2) AS damage_cost,
                CASE WHEN st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id THEN
                    CASE WHEN (barz.purchase_type IS NULL AND barz.distribution_type IS NULL AND barz.storage_type IS NULL) THEN SUM(COALESCE(quant.qty, 0.0))
                        ELSE COALESCE((quant.qty / barz.factor), 0.0)
                    END
                ELSE 0 END AS damage_quantity,
                (
                    SELECT COUNT(st_move.id)
                        FROM stock_move st_move
                    WHERE
                        st_move.location_id = warehouse.damage_src_location_id AND st_move.location_dest_id = warehouse.damage_dest_location_id
                        AND {move_product_string} AND st_move.date >= '{start_date}' AND st_move.date <= '{end_date}' AND st_move.state = 'done'
                ) AS ticket_count,
                pt.name AS product_name,
                st_move.id AS move_id,
                st_move.product_uom_qty,
                barz.partner_name,
                warehouse.company_id AS company_id,
                warehouse.damage_src_location_id AS damage_src_location_id,
                warehouse.damage_dest_location_id AS loss_dest_location_id
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
                  AND
                    CASE WHEN st_move.vendor_id IS NOT NULL THEN
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
                barz.purchase_type,
                barz.distribution_type,
                barz.storage_type,
                warehouse.company_id,
                st_move.id,
                quant.id
            """.format(**args)
        self.env.cr.execute(query)
        result = self.env.cr.fetchall()
        self.env.cr.execute("""DELETE FROM inventory_categ_uom_type""")
        return result

    def bind_data(self, ws, report_data, report):
        ws.set_column(0, 20, 30)
        row = 14
        ws.write(row, 0, 'Warehouse', self.styles['table_header'])
        ws.write(row, 1, '# of Stock Move', self.styles['table_header'])
        # ws.write(row, 2, 'Date of Inventory Adjustment', self.styles['table_header'])
        ws.write(row, 2, 'Total Damage', self.styles['table_header'])

        perc = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        categ_columns = {}
        categ_datas = defaultdict(list)
        categ_datas1 = defaultdict(list)
        uom_categ = {}

        col = 3
        tot_warehouse = {}
        warehouse_data1 = {}
        final_category_ids = []
        row -= 2

        for categ in report.inv_categ_uom_ids:
            uom_categ[categ.uom_categ_id.id] = categ.uom_type

        for data in report_data:
            categ_datas[data[3]].append(data)
            categ_datas1[data[0]].append(data)

        for key, value in categ_datas.items():
            row_value = value[0]
            if len(value) < 1:
                continue

            # Add in Columns Dict
            categ_columns.update({
                key: {
                    'damage': [col, col + 1],
                }
            })

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

            ws.merge_range(row, col, row, col + 1, categ_name, self.styles['table_header'])
            ws.merge_range(row+1, col, row+1, col+1, 'Damage', self.styles['table_header'])
            ws.write(row+2, col, 'Qty', self.styles['table_header'])
            ws.write(row+2, col+1, 'Amount', self.styles['table_header'])
            col += 2
        row += 3

        warehouse_data1 = {}
        for key, value in categ_datas1.items():
            tot_warehouse.setdefault(key, {
                'damage': 0,
                'number_move': 0.0
            })
            for v in value:
                final_category_ids.append(v[3])
                tot_warehouse[key]['damage'] += v[4]
                # tot_warehouse[key]['number_move'] += v[6]
                if warehouse_data1.get(key):
                    if warehouse_data1[key]['categs'].get(v[3]):
                        warehouse_data1[key]['categs'][v[3]]['tot_damage'] += round(v[4], 2)
                        warehouse_data1[key]['categs'][v[3]]['damage_quantity'] += round(v[5], perc)
                        # warehouse_data1[key]['categs'][v[3]]['number_st'] += v[6]
                    else:
                        warehouse_data1[key]['categs'].update({v[3]: {
                            # 'number_st': v[6],
                            'tot_damage': round(v[4], 2),
                            'damage_quantity': round(v[5], perc),
                        }})
                else:
                    _vals = {}
                    _vals.update({
                            'warehouse_name': v[1],
                            'number_st': v[6],
                            # 'number_date': v[6],
                            'categs': {
                                v[3]: {
                                    'damage_quantity': round(v[5], perc),
                                    'tot_damage': round(v[4], 2),
                                    }
                                }
                            })
                    warehouse_data1.update({
                        key: _vals
                    })

        final_categ_ids = list(set(final_category_ids))

        for wid, data in warehouse_data1.iteritems():
            all_category = data.get('categs')
            # set zero value to which category not exits in warehoues
            for fkey in final_categ_ids:
                if not all_category.get(fkey):
                    all_category.setdefault(fkey, {
                        'damage_quantity': 0,
                        'tot_damage': 0.0
                    })
            wh_grand_tot = tot_warehouse.get(wid)
            col = 0
            ws.write(row, col, data['warehouse_name'], self.styles['table_row_left'])
            col += 1
            # total_move = wh_grand_tot.get('number_move')
            ws.write(row, col, data['number_st'], self.styles['table_row_left'])
            # col += 1
            # ws.write(row, col, data['number_date'], self.styles['table_row_left'])
            grand_damage = wh_grand_tot.get('damage')
            col += 1
            ws.write(row, col, grand_damage, self.styles['table_row_right'])
            for key, by_category in all_category.iteritems():
                ws.write(row, categ_columns[key]['damage'][0], by_category.get('damage_quantity'), self.styles['table_row_right'])
                ws.write(row, categ_columns[key]['damage'][1], by_category.get('tot_damage'), self.styles['table_row_right'])
            row += 1

stock_inventory_adj_damage_report('report.stock_inventory_adj.stock_inventory_adj_damage_report', 'stock.inventory.damage.wizard')
