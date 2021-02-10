from datetime import datetime, date, timedelta
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from collections import OrderedDict

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class ReportInventoryDetails(ReportXlsx):
    _name = 'report.inventory.details'

    def generate_xlsx_report(self, wb, data, report):
        ws = wb.add_worksheet('Inventory Details Report')
        self.set_paper(wb, ws)
        self.styles = self.get_report_styles(wb)
        self.set_header(ws, report)
        domain = self.get_domain(report)
        report_data = self.get_data(domain, report)
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

    def set_header(self, ws, report):
        ws.write('A1', u'Start Date', self.styles['bold'])
        ws.write_datetime('B1', datetime.strptime(report.start_date, DATE_FORMAT), self.styles['date_left'])
        ws.write('A2', u'End Date', self.styles['bold'])
        ws.write_datetime('B2', datetime.strptime(report.end_date, DATE_FORMAT), self.styles['date_left'])
        ws.write('A3', u'Warehouse(s)', self.styles['bold'])
        ws.write('B3', ', '.join([w.name for w in report.warehouse_ids]))
        ws.write('A4', u'Location(s)', self.styles['bold'])
        ws.write('B4', ', '.join([l.complete_name for l in report.location_ids]))
        ws.write('A5', u'Product Category(s)', self.styles['bold'])
        ws.write('B5', ', '.join([l.complete_name for l in report.product_categ_ids]))
        ws.write('A6', u'Product(s)', self.styles['bold'])
        ws.write('B6', ', '.join([l.name for l in report.product_ids]))
        ws.write('A7', u'Period', self.styles['bold'])
        ws.write('B7', report.period)
        ws.write('A8', u'UOM Type', self.styles['bold'])
        ws.write('B8', report.uom_type)
        ws.write('A9', u'Report Type', self.styles['bold'])
        ws.write('B9', report.report_type)

    def get_timerange(self, report):
        """
        @param report: report object
        @return: Time range based on period.
        eg:  01/01/2017 - 03/01/2017 will return ['01/01/2017', '02/01/2017', '03/01/2017'] with period is daily
        """
        date_range = []
        period = report.period
        start_date = datetime.strptime(report.start_date, DATE_FORMAT)
        end_date = datetime.strptime(report.end_date, DATE_FORMAT)
        day_lap = timedelta(days=1)
        while start_date <= end_date:
            if period == 'daily':
                if start_date.strftime('%Y-%m-%d') not in date_range:
                    date_range.append(start_date.strftime('%Y-%m-%d'))
            elif period == 'weekly':
                if start_date.strftime('%W-%Y') not in date_range:
                    date_range.append(start_date.strftime('%W-%Y'))
            elif period == 'monthly':
                if start_date.strftime('%m-%Y') not in date_range:
                    date_range.append(start_date.strftime('%m-%Y'))
            elif period == 'quarterly':
                quarter = "%s-%s" % ((start_date.month - 1) // 3, start_date.year)
                if quarter not in date_range:
                    date_range.append(quarter)
            start_date += day_lap
        return date_range

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

    def get_locations(self, report):
        locations = report.location_ids
        stock_location = self.env['stock.location']
        if not locations:
            if report.warehouse_ids:
                view_locations = [x.view_location_id.id for x in report.warehouse_ids]
                locations = stock_location.search([('id', 'child_of', view_locations)])
            else:
                if report.transit_loc:
                    locations = stock_location.search([('usage', '=', 'transit')])
                elif report.warehouse_type:
                    outlet_locations = [x.warehouse_id.view_location_id.id for x in self.env['br_multi_outlet.outlet'].search([])]
                    if report.warehouse_type == 'outlet_wh':
                        locations = stock_location.search([('id', 'child_of', outlet_locations)])
                    elif report.warehouse_type == 'hq_wh':
                        locations = stock_location.search(['!', ('id', 'child_of', outlet_locations)])
        return locations

    def get_flush_date(self):
        """
        Get the latest flush date.
        """
        latest_flush_date = self.env['stock.flush.date'].search(
            [], order='flush_date desc', limit=1)
        if latest_flush_date:
            return latest_flush_date.flush_date
        return False

    def get_period_by_date(self, period, _date):
        d = datetime.strptime(_date, DATE_FORMAT)
        if period == 'daily':
            return _date
        elif period == 'weekly':
            return d.strftime("%W-%Y")
        elif period == 'monthly':
            return d.strftime("%Y-%m")
        elif period == 'quarterly':
            return "%s-%s" % ((d.month - 1) // 3, d.year)

    def get_data(self, domain, report):
        statements = {
            'select': self.select(),
            'group_by': self.group_by(),
            'where': self.where(report),
            'main_query': self.get_main_query(domain),
        }
        query = self.get_query(statements)
        self.env.cr.execute(query)  
        result = self.env.cr.dictfetchall()
        return result

    def get_query(self, args):
        query = """
        WITH tmp AS (
            SELECT
              {select}
            FROM stock_move move
              LEFT JOIN stock_quant_move_rel ON move.id = stock_quant_move_rel.move_id
              LEFT JOIN stock_quant quant ON quant.id = stock_quant_move_rel.quant_id
              LEFT JOIN product_product pp ON move.product_id = pp.id
              LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
            {where}
            {group_by}
        ){main_query}
        """.format(**args)
        return query

    def where(self, report):
        wheres = {
            'start_date': report.start_date,
            'end_date': report.end_date,
            'location_ids': '',
            'product_ids': '',
        }

        def _in_condition(obs):
            ids = ['(%s)' % p.id for p in obs]
            ids_string = ", ".join(ids)
            return ids_string

        product_templates = report.product_ids
        if report.product_categ_ids and not product_templates:
            categ_ids = [x.id for x in report.product_categ_ids]
            product_templates = self.env['product.template'].search([('categ_id', 'child_of', categ_ids)])

        if product_templates:
            product_template_ids = [x.id for x in product_templates]
            products = self.env['product.product'].search([('product_tmpl_id', 'in', product_template_ids)])
            wheres['product_ids'] = _in_condition(products)

        flush_date = self.get_flush_date()
        wheres['flush_date'] = "AND 1=1"
        if flush_date:
            wheres['flush_date'] = "AND (pt.is_asset OR move.date >= '%s')" % flush_date

        locations = self.get_locations(report)
        if locations:
            wheres['location_ids'] = _in_condition(locations)

        if wheres['location_ids']:
            wheres['location_ids'] = "AND (move.location_id = ANY (VALUES {location_ids}) OR move.location_dest_id = ANY (VALUES {location_ids}))".format(location_ids=wheres['location_ids'])
        if wheres['product_ids']:
            wheres['product_ids'] = "AND move.product_id = ANY (VALUES %s)" % wheres['product_ids']

        where_sql = """WHERE
            date(move.date) <= date('{end_date}')
            {location_ids}
            {product_ids}
            {flush_date}
        """.format(**wheres)
        return where_sql

    def select(self):
        return "*"

    def group_by(self):
        return ""

    def get_domain(self, report):
        return {}

    def bind_data(self, ws, report_data, report):
        return UserWarning("Missing binding report data !")

    def get_main_query(self, domain):
        return UserWarning("Missing main query !")

class ReportInventoryDetailsBalance(ReportInventoryDetails):
    _name = 'report.inventory.details.balance'

    def get_domain(self, report):
        uom_fields = {
            'standard': '1 = 2',
            'distribution': 'supplier_uom.is_distribution = TRUE',
            'storage': 'supplier_uom.is_storage = TRUE',
        }
        locations = self.get_locations(report)
        location_ids = ", ".join(['(%s)' % p.id for p in locations])
        if location_ids:
            location_ids = 'VALUES ' + location_ids

        domain = {
            'start_date': report.start_date,
            'end_date': report.end_date,
            'uom_type_cond': uom_fields[report.uom_type],
            # If location_ids is empty, get all location
            'location_dest_ids': 'destination_location_id = ANY(%s)' % location_ids if location_ids else '1=1',
            'location_src_ids': 'source_location_id = ANY(%s)' % location_ids if location_ids else '1=1'
        }
        return domain

    def get_data(self, domain, report):
        def key_by_period(_date):
            d = datetime.strptime(_date, DATE_FORMAT)
            if period == 'daily':
                return _date
            elif period == 'weekly':
                return d.strftime("%W-%Y")
            elif period == 'monthly':
                return d.strftime("%m-%Y")
            elif period == 'quarterly':
                return "%s-%s" % ((d.month - 1) // 3, d.year)

        period = report.period
        raw_data = super(ReportInventoryDetailsBalance, self).get_data(domain, report)
        res = OrderedDict()

        for l in raw_data:
            k = '{location_id}|{lot_id}|{product_id}'.format(
                location_id=l['location_id'] if 'location_id' in l else None,
                lot_id=l['lot_id'],
                product_id=l['product_id'],
            )
            date_key = key_by_period(l['date'])
            if k not in res:
                l['dates'] = {}
                l['dates'][date_key] = {
                    'opening_qty': l['opening_qty'] or 0,
                    'opening_value': l['opening_value'] or 0,
                    'qty_in': l['qty_in'] or 0,
                    'qty_out': l['qty_out'] or 0,
                    'value_in': l['value_in'] or 0,
                    'value_out': l['value_out'] or 0,
                }
                res[k] = l
            else:
                if date_key in res[k]['dates']:
                    res[k]['dates'][date_key]['qty_in'] += l['qty_in'] or 0
                    res[k]['dates'][date_key]['qty_out'] += l['qty_out'] or 0
                    res[k]['dates'][date_key]['value_in'] += l['value_in'] or 0
                    res[k]['dates'][date_key]['value_out'] += l['value_out'] or 0
                else:
                    res[k]['dates'][date_key] = {
                        'qty_in': l['qty_in'] or 0,
                        'qty_out': l['qty_out'] or 0,
                        'value_in': l['value_in'] or 0,
                        'value_out': l['value_out'] or 0
                    }
        return res

    def bind_data(self, ws, report_data, report):
        period_time_range = self.get_timerange(report)
        period = report.period
        ws.set_column(0, 20, 30)
        row = 14
        ws.write(row, 0, 'Warehouse', self.styles['table_header'])
        ws.write(row, 1, 'Location', self.styles['table_header'])
        ws.write(row, 2, 'Date/Week/Month', self.styles['table_header'])
        ws.write(row, 3, 'Product Category L1', self.styles['table_header'])
        ws.write(row, 4, 'Product Category L2', self.styles['table_header'])
        ws.write(row, 5, 'Product Category L3', self.styles['table_header'])
        ws.write(row, 6, 'Product Category L4', self.styles['table_header'])
        ws.write(row, 7, 'Product', self.styles['table_header'])
        ws.write(row, 8, 'Lot Number', self.styles['table_header'])
        ws.write(row, 9, 'UOM', self.styles['table_header'])
        ws.write(row, 10, 'Supplier', self.styles['table_header'])
        ws.write(row, 11, "Opening Balance - Qty", self.styles['table_header'])
        ws.write(row, 12, "Opening Balance - Value", self.styles['table_header'])
        ws.write(row, 13, "Stock In - Qty", self.styles['table_header'])
        ws.write(row, 14, "Stock In - Value", self.styles['table_header'])
        ws.write(row, 15, "Stock Out - Qty", self.styles['table_header'])
        ws.write(row, 16, "Stock Out - Value", self.styles['table_header'])
        ws.write(row, 17, "Closing Balnce - Qty", self.styles['table_header'])
        ws.write(row, 18, "Closing Balnce - Value", self.styles['table_header'])
        ws.write(row, 19, "Into the System Date", self.styles['table_header'])
        ws.write(row, 20, "Removal Date", self.styles['table_header'])
        row += 1

        # Print all data for each set of "location", "lot" and "product" in selected date range
        for k in report_data.keys():
            line = report_data[k]
            closing_qty = 0
            closing_value = 0
            for dt in period_time_range:
                ws.write(row, 0, line['warehouse_name'], self.styles['table_row_left'])
                ws.write(row, 1, line['location_name'], self.styles['table_row_left'])
                if period == 'daily':
                    ws.write_datetime(row, 2, datetime.strptime(dt, DATE_FORMAT), self.styles['table_row_datetime'])
                else:
                    ws.write(row, 2, dt, self.styles['table_row_right'])

                # Split product category's complete name to get level(s) of category
                product_category = line['product_category'].split(" / ")
                categ_len = len(product_category)
                col = 3
                for i in range(0, 4):
                    if i < categ_len:
                        ws.write(row, col, product_category[i], self.styles['table_row_left'])
                    else:
                        ws.write(row, col, ' ', self.styles['table_row_left'])
                    col += 1

                ws.write(row, 7, line['product_name'], self.styles['table_row_left'])
                ws.write(row, 8, line['lot_name'], self.styles['table_row_left'])
                ws.write(row, 9, line['uom'], self.styles['table_row_left'])
                ws.write(row, 10, line['supplier'], self.styles['table_row_left'])

                if dt in line['dates']:
                    if 'opening_qty' in line['dates'][dt]:
                        opening_qty = line['dates'][dt]['opening_qty']
                        opening_value = line['dates'][dt]['opening_value']
                    else:
                        opening_qty = closing_qty
                        opening_value = closing_value
                    qty_in = line['dates'][dt]['qty_in'] or 0
                    qty_out = line['dates'][dt]['qty_out'] or 0
                    value_in = line['dates'][dt]['value_in'] or 0
                    value_out = line['dates'][dt]['value_out'] or 0
                else:
                    opening_qty = closing_qty
                    opening_value = closing_value
                    qty_in = 0
                    qty_out = 0
                    value_in = 0
                    value_out = 0

                closing_qty = opening_qty + qty_in + qty_out
                closing_value = opening_value + value_in + value_out
                ws.write(row, 11, opening_qty, self.styles['table_row_right'])
                ws.write(row, 12, opening_value, self.styles['table_row_right'])

                ws.write(row, 13, qty_in, self.styles['table_row_right'])
                ws.write(row, 14, value_in, self.styles['table_row_right'])

                ws.write(row, 15, qty_out, self.styles['table_row_right'])
                ws.write(row, 16, value_out, self.styles['table_row_right'])

                ws.write(row, 17, closing_qty, self.styles['table_row_right'])
                ws.write(row, 18, closing_value, self.styles['table_row_right'])
                if line['into_system_date']:
                    ws.write_datetime(row, 19, datetime.strptime(line['into_system_date'], DATETIME_FORMAT), self.styles['table_row_datetime'])
                else:
                    ws.write(row, 19, '', self.styles['table_row_datetime'])
                if line['removal_date']:
                    ws.write_datetime(row, 20, datetime.strptime(line['removal_date'], DATETIME_FORMAT), self.styles['table_row_datetime'])
                else:
                    ws.write(row, 20, '', self.styles['table_row_datetime'])
                row += 1

    def get_main_query(self, domain):
        main_query = """
        , foo AS (
            SELECT
                destination_location_id AS location_id,
                lot_id,
                product_id,
                value,
                qty,
                date
            FROM tmp
            WHERE {location_dest_ids}
            UNION ALL
            SELECT
                source_location_id AS location_id,
                lot_id,
                product_id,
                value,
                -1 * qty,
                date
            FROM tmp
            WHERE {location_src_ids}
        ), opening AS (
            SELECT
                location_id,
                lot_id,
                product_id,
                SUM(qty) AS qty,
                SUM(qty * value) AS value,
                date('{start_date}') AS date
            FROM foo
            WHERE date(foo.date) < date('{start_date}')
            GROUP BY
                location_id,
                lot_id,
                product_id
        ), moves AS (
            SELECT
                location_id,
                lot_id,
                product_id,
                SUM(CASE WHEN qty < 0 THEN qty * value ELSE 0 END) AS value_out,
                SUM(CASE WHEN qty > 0 THEN qty * value ELSE 0 END) AS value_in,
                SUM(qty) AS qty,
                SUM(CASE WHEN qty < 0 THEN qty ELSE 0 END) AS qty_out,
                SUM(CASE WHEN qty > 0 THEN qty ELSE 0 END) AS qty_in,
                date(date) as date
            FROM foo
            WHERE date(foo.date) >= date('{start_date}')
            GROUP BY
                location_id,
                lot_id,
                product_id,
                date(date)
        )
        SELECT
          location.id AS location_id,
          lot.id AS lot_id,
          product.id AS product_id,
          warehouse.name                     AS warehouse_name,
          location.complete_name             AS location_name,
          product_category.complete_name     AS product_category,
          product.name_template              AS product_name,
          lot.name                           AS lot_name,
          lot.removal_date::TIMESTAMP(0) + INTERVAL '8 HOURS' AS removal_date,
          lot.create_date::TIMESTAMP(0) + INTERVAL '8 HOURS'  AS into_system_date,
          CASE WHEN barz.name IS NOT NULL THEN barz.name ELSE base_uom.name END AS uom,
          CASE WHEN barz.name IS NOT NULL THEN barz.supplier_name ELSE base_supplier.name END AS supplier,
          CASE WHEN opening.qty IS NULL THEN 0 ELSE CASE WHEN barz.factor IS NOT NULL THEN opening.qty / barz.factor ELSE opening.qty END END                      AS opening_qty,
          CASE WHEN opening.value IS NULL THEN 0 ELSE CASE WHEN barz.factor IS NOT NULL THEN opening.value / barz.factor ELSE opening.value END END                      AS opening_value,
          CASE WHEN barz.factor IS NOT NULL THEN moves.qty_out / barz.factor ELSE moves.qty_out END AS qty_out,
          CASE WHEN barz.factor IS NOT NULL THEN moves.value_out / barz.factor ELSE moves.value_out END AS value_out,
          CASE WHEN barz.factor IS NOT NULL THEN moves.qty_in / barz.factor ELSE moves.qty_in END AS qty_in,
          CASE WHEN barz.factor IS NOT NULL THEN moves.value_in / barz.factor ELSE moves.value_in END AS value_in,
          CASE WHEN moves.date IS NULL THEN opening.date ELSE moves.date END              AS date
        FROM moves
          FULL JOIN opening
            ON moves.location_id = opening.location_id
               AND moves.lot_id = opening.lot_id
               AND moves.product_id = opening.product_id
          INNER JOIN stock_location location ON moves.location_id = location.id OR opening.location_id = location.id
          LEFT JOIN stock_location parent_location
            ON parent_location.parent_left < location.parent_left
               AND parent_location.parent_right > location.parent_left
               AND location.id != parent_location.location_id
               AND parent_location.usage = 'view'
          LEFT JOIN stock_warehouse warehouse ON parent_location.id = warehouse.view_location_id
          INNER JOIN product_product product ON moves.product_id = product.id OR opening.product_id = product.id
          INNER JOIN product_template ON product_template.id = product.product_tmpl_id
          INNER JOIN product_category ON product_template.categ_id = product_category.id
          LEFT JOIN stock_production_lot lot ON moves.lot_id = lot.id OR opening.lot_id = lot.id
          LEFT JOIN (
            SELECT
               supplierinfo.product_tmpl_id,
               supplier_uom.name,
               supplier.name AS supplier_name,
               supplier_uom.factor AS factor
            FROM
               product_supplierinfo supplierinfo
              INNER JOIN product_uom supplier_uom ON supplierinfo.id = supplier_uom.vendor_id
              AND {uom_type_cond}
              LEFT JOIN res_partner supplier ON supplierinfo.name = supplier.id
          ) barz ON product_template.id = barz.product_tmpl_id
          LEFT JOIN product_uom base_uom ON product_template.uom_id = base_uom.id
          LEFT JOIN product_supplierinfo base_supplierinfo ON base_uom.vendor_id = base_supplierinfo.id
          LEFT JOIN res_partner base_supplier ON base_supplierinfo.name = base_supplier.id
        ORDER BY
            warehouse.name,
            location.complete_name,
            product_category.complete_name,
            product.name_template,
            moves.date,
            lot.name

        """.format(**domain)
        return main_query

    def select(self):
        select_str = """
           move.product_uom,
           move.picking_id,
           move.state,
           move.origin,
           move.location_id                   AS source_location_id,
           move.location_dest_id              AS destination_location_id,
           quant.lot_id,
           move.product_id,
           CASE WHEN quant.cost IS NOT NULL THEN quant.cost ELSE 0 END                        AS value,
           SUM(CASE WHEN quant.qty > 0 THEN quant.qty ELSE 0 END) AS qty,
           move.date + INTERVAL '8 HOURS'     AS date,
           move.date_expected + INTERVAL '8 HOURS' AS date_expected
           """
        return select_str

    def where(self, report):
        where_str = super(ReportInventoryDetailsBalance, self).where(report)
        where_str += " AND move.state = 'done'"
        return where_str

    def group_by(self):
        group_by_str = """
        GROUP BY
          move.product_uom,
          move.picking_id,
          move.state,
          move.origin,
          move.location_id,
          move.location_dest_id,
          move.product_id,
          move.date,
          move.date_expected,
          quant.lot_id,
          quant.cost
        """
        return group_by_str

ReportInventoryDetailsBalance('report.inventory.details.balance', 'inventory.details.report')

class ReportInventoryDetailsMovement(ReportInventoryDetails):
    _name = 'report.inventory.details.movement'

    def bind_data(self, ws, report_data, report):
        ws.set_column(0, 23, 30)
        row = 14
        ws.write(row, 0, 'Warehouse', self.styles['table_header'])
        ws.write(row, 1, 'Transfer No.', self.styles['table_header'])
        ws.write(row, 2, 'Source Document', self.styles['table_header'])
        ws.write(row, 3, 'Back Order', self.styles['table_header'])
        ws.write(row, 4, 'Scheduled Date', self.styles['table_header'])
        ws.write(row, 5, 'Validated Date', self.styles['table_header'])
        ws.write(row, 6, 'Product Category L1', self.styles['table_header'])
        ws.write(row, 7, 'Product Category L2', self.styles['table_header'])
        ws.write(row, 8, 'Product Category L3', self.styles['table_header'])
        ws.write(row, 9, 'Product Category L4', self.styles['table_header'])
        ws.write(row, 10, 'Product', self.styles['table_header'])
        ws.write(row, 11, 'Source Location', self.styles['table_header'])
        ws.write(row, 12, 'Destination Location', self.styles['table_header'])
        ws.write(row, 13, 'UOM', self.styles['table_header'])
        ws.write(row, 14, 'Supplier', self.styles['table_header'])
        ws.write(row, 15, 'Qty', self.styles['table_header'])
        ws.write(row, 16, 'Value', self.styles['table_header'])
        ws.write(row, 17, 'Status', self.styles['table_header'])
        ws.write(row, 18, 'User UOM', self.styles['table_header'])
        ws.write(row, 19, 'Qty (User UOM)', self.styles['table_header'])
        # ws.write(row, 20, 'Value (User UOM)', self.styles['table_header'])
        ws.write(row, 20, 'Standard UOM', self.styles['table_header'])
        ws.write(row, 21, 'Qty (Standard UOM)', self.styles['table_header'])
        # ws.write(row, 23, 'Value (Standard UOM)', self.styles['table_header'])
        row += 1
        for line in report_data:
            ws.write(row, 0, line['warehouse_name'], self.styles['table_row_left'])
            ws.write(row, 1, line['transfer_no'], self.styles['table_row_left'])
            ws.write(row, 2, line['source_document'], self.styles['table_row_left'])
            ws.write(row, 3, line['back_order'], self.styles['table_row_left'])
            ws.write_datetime(row, 4, datetime.strptime(line['scheduled_date'], DATETIME_FORMAT), self.styles['table_row_datetime'])
            ws.write_datetime(row, 5, datetime.strptime(line['validate_date'], DATETIME_FORMAT), self.styles['table_row_datetime'])

            # Split product category's complete name to get level(s) of category
            product_category = line['product_category'].split(" / ")
            categ_len = len(product_category)
            col = 6
            for i in range(0, 4):
                if i < categ_len:
                    ws.write(row, col, product_category[i], self.styles['table_row_left'])
                else:
                    ws.write(row, col, ' ', self.styles['table_row_left'])
                col += 1

            ws.write(row, 10, line['product_name'], self.styles['table_row_left'])
            ws.write(row, 11, line['source_location'], self.styles['table_row_left'])
            ws.write(row, 12, line['dest_location'], self.styles['table_row_left'])
            ws.write(row, 13, line['uom_name'], self.styles['table_row_left'])
            ws.write(row, 14, line['supplier_name'], self.styles['table_row_left'])
            ws.write(row, 15, line['qty'], self.styles['table_row_right'])
            ws.write(row, 16, line['qty'] * line['value'], self.styles['table_row_right'])
            ws.write(row, 17, line['state'], self.styles['table_row_left'])
            ws.write(row, 18, line['user_uom_name'], self.styles['table_row_left'])
            ws.write(row, 19, line['user_uom_qty'], self.styles['table_row_right'])
            # ws.write(row, 20, line['user_uom_qty'] * line['value'], self.styles['table_row_right'])
            ws.write(row, 20, line['standard_uom_name'], self.styles['table_row_left'])
            ws.write(row, 21, line['standard_uom_qty'], self.styles['table_row_right'])
            # ws.write(row, 23, line['standard_uom_qty'] * line['value'], self.styles['table_row_right'])
            row += 1

    def get_domain(self, report):
        uom_fields = {
            'standard': '1 = 2',
            'distribution': 'supplier_uom.is_distribution = TRUE',
            'storage': 'supplier_uom.is_storage = TRUE',
        }

        domain = {
            'uom_type_cond': uom_fields[report.uom_type],
        }
        return domain

    def get_main_query(self, domain):
        main_query = """
        SELECT
          tmp.state,
          warehouse.name AS warehouse_name,
          picking.name AS transfer_no,
          tmp.origin AS source_document,
          backorder.name AS back_order,
          tmp.date_expected AS scheduled_date,
          tmp.date AS validate_date,
          product_category.complete_name AS product_category,
          product.name_template AS product_name,
          source_location.complete_name AS source_location,
          dest_location.complete_name AS dest_location,
          uom.name AS user_uom_name,
          barz.supplier_name,
          tmp.move_qty AS user_uom_qty,
          tmp.value,
          CASE WHEN barz.name IS NOT NULL THEN barz.name ELSE standard_uom.name END AS uom_name,
          CASE WHEN barz.factor IS NOT NULL THEN tmp.qty / barz.factor ELSE tmp.qty END AS qty,
          standard_uom.name AS standard_uom_name,
          tmp.standard_uom_qty AS standard_uom_qty
        FROM tmp
          INNER JOIN stock_location dest_location ON tmp.destination_location_id = dest_location.id
          INNER JOIN stock_location source_location ON tmp.source_location_id = source_location.id
          LEFT JOIN stock_location parent_location
            ON parent_location.parent_left < source_location.parent_left
               AND parent_location.parent_right > source_location.parent_left
               AND source_location.id != parent_location.location_id
               AND parent_location.usage = 'view'
          LEFT JOIN stock_warehouse warehouse ON parent_location.id = warehouse.view_location_id
          LEFT JOIN product_uom uom ON uom.id = tmp.product_uom
          LEFT JOIN stock_picking picking ON picking.id = tmp.picking_id
          LEFT JOIN stock_picking backorder ON picking.backorder_id = backorder.id
          LEFT JOIN product_product product ON product.id = tmp.product_id
          LEFT JOIN product_template ON product.product_tmpl_id = product_template.id
          LEFT JOIN product_category ON product_template.categ_id = product_category.id
          LEFT JOIN product_uom standard_uom ON product_template.uom_id = standard_uom.id
          LEFT JOIN (
            SELECT
               supplierinfo.product_tmpl_id,
               supplier_uom.name,
               supplier.name AS supplier_name,
               supplier_uom.factor AS factor
            FROM
               product_supplierinfo supplierinfo
              INNER JOIN product_uom supplier_uom ON supplierinfo.id = supplier_uom.vendor_id
              AND {uom_type_cond}
              LEFT JOIN res_partner supplier ON supplierinfo.name = supplier.id
          ) barz ON product_template.id = barz.product_tmpl_id
          LEFT JOIN stock_production_lot lot ON tmp.lot_id = lot.id
        ORDER BY
          warehouse.name,
          source_location.complete_name,
          dest_location.complete_name,
          product_category.complete_name,
          product.name_template,
          lot.name,
          tmp.date;
        """.format(**domain)
        return main_query

    def where(self, report):
        where_str = super(ReportInventoryDetailsMovement, self).where(report)
        where_str += " AND date(move.date) >= date('{start_date}')".format(start_date=report.start_date)
        return where_str

    def select(self):
        select_str = """
           move.product_uom,
           move.picking_id,
           move.state,
           move.origin,
           move.location_id                   AS source_location_id,
           move.location_dest_id              AS destination_location_id,
           quant.lot_id,
           move.product_id,
           CASE WHEN quant.cost IS NOT NULL THEN quant.cost ELSE 0 END                        AS value,
           SUM(CASE WHEN quant.qty > 0 THEN quant.qty ELSE 0 END) AS qty,
           MAX(move.product_qty)                                  AS standard_uom_qty,
           MAX(move.product_uom_qty)          AS move_qty,
           move.date + INTERVAL '8 HOURS'     AS date,
           move.date_expected + INTERVAL '8 HOURS' AS date_expected
           """
        return select_str

    def group_by(self):
        group_by_str = """
        GROUP BY
          move.product_uom,
          move.picking_id,
          move.state,
          move.origin,
          move.location_id,
          move.location_dest_id,
          move.product_id,
          move.date,
          move.date_expected,
          quant.lot_id,
          quant.cost
        """
        return group_by_str

ReportInventoryDetailsMovement('report.inventory.details.movement', 'inventory.details.report')
