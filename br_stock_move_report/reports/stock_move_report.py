from datetime import datetime, date, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp import api, fields, models, exceptions, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import logging

_logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class StockMoveReportWizard(models.TransientModel):
    _name = 'stock.move.report.wizard'

    location_ids = fields.Many2many(comodel_name='stock.location', relation='stock_move_src_location_rel', column1='report_id', column2='location_id', string='Source Location')
    location_dest_ids = fields.Many2many(comodel_name='stock.location', relation='stock_move_dest_location_rel', column1='report_id', column2='location_id', string='Destination Location')
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    product_categ_ids = fields.Many2many(string='Product Category', comodel_name='product.category', required=True)
    product_ids = fields.Many2many(string='Product', comodel_name='product.template')

    @api.constrains('start_date', 'end_date')
    def date_range(self):
        if self.start_date and self.end_date:
            if datetime.strptime(self.start_date, DEFAULT_SERVER_DATE_FORMAT) > datetime.strptime(self.end_date, DEFAULT_SERVER_DATE_FORMAT):
                raise exceptions.ValidationError(_('End date must be greater than start date !'))

    @api.onchange('product_categ_ids')
    def onchange_product_categ_ids(self):
        res = {'domain': {'product_ids': []}}
        if self.product_categ_ids:
            res['domain']['product_ids'] = [('categ_id', 'child_of', [categ.id for categ in self.product_categ_ids])]
        return res

    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_stock.br_stock_move_report')

class br_stock_move_report(ReportXlsx):
    _name = 'report.br_stock.br_stock_move_report'

    def generate_xlsx_report(self, wb, data, report):
        ws = wb.add_worksheet('Stock Move')
        self.set_paper(wb, ws)
        self.styles = self.get_report_styles(wb)
        self.set_header(ws)
        report_data = self.get_data(report)
        self.bind_data(wb, ws, report_data, report)

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
        ws.set_column(0, 0, 25)
        ws.set_column(1, 1, 20)
        ws.set_column(2, 2, 40)
        ws.set_column(3, 3, 40)
        ws.set_column(4, 5, 15)
        ws.set_column(6, 7, 25)
        ws.set_column(8, 9, 25)
        ws.set_column(10, 10, 20)

    def set_header(self, ws):

        ws.write('A1', u'Reference', self.styles['table_header'])
        ws.write('B1', u'Source Document', self.styles['table_header'])
        ws.write('C1', u'Product Category', self.styles['table_header'])
        ws.write('D1', u'Product', self.styles['table_header'])
        # ws.write('E1', u'Unit Price', self.styles['table_header'])
        ws.write('E1', u'Quantity', self.styles['table_header'])
        ws.write('F1', u'UOM', self.styles['table_header'])
        ws.write('G1', u'Source Location', self.styles['table_header'])
        ws.write('H1', u'Destination Location', self.styles['table_header'])
        ws.write('I1', u'Date', self.styles['table_header'])
        ws.write('J1', u'Expected Date', self.styles['table_header'])
        ws.write('K1', u'Status', self.styles['table_header'])

    def get_report_styles(self, wb):
        styles = {}

        styles['bold'] = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })

        styles['amount'] = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman'
        })

        styles['normal'] = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
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
            'bg_color': '#7FE4EF',
        })
        return styles

    def get_data(self, report):
        statements = self.where(report)

        query = """
            SELECT
                sp.name AS reference,
                sm.origin AS source_document,
                pc.complete_name AS product_category,
                pp.name_template AS product,
                --sm.price_unit AS unit_price,
                sm.product_uom_qty AS quantity,
                pu.name AS uom,
                sl1.complete_name AS source_location,
                sl2.complete_name AS dest_location,
                DATE(sm.date + INTERVAL '8 HOUR') AS date,
                DATE(sm.date_expected + INTERVAL '8 HOUR') AS date_expected,
                sm.state AS status
            FROM stock_move sm
                JOIN stock_picking sp ON sm.picking_id = sp.id
                JOIN product_product pp ON sm.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                JOIN product_category pc ON pt.categ_id = pc.id
                JOIN product_uom pu ON sm.product_uom = pu.id
                JOIN stock_location sl1 ON sm.location_id = sl1.id
                JOIN stock_location sl2 ON sm.location_dest_id = sl2.id
            WHERE sm.date BETWEEN '{start_date}' AND '{end_date}'
                {location_ids}
                {location_dest_ids}
                {product_ids}
            ORDER BY sm.date
        """.format(**statements)
        _logger.info("Q start time ---> %s" % datetime.now())
        _logger.info("Query ---> %s" % query)
        self.env.cr.execute(query)
        _logger.info("Q end time ---> %s" % datetime.now())
        raw_data = self.env.cr.dictfetchall()
        return raw_data

    def bind_data(self, wb, ws, report_data, report):
        row = 0
        col = 0
        count = 0
        for line in report_data:
            row += 1
            col = 0
            if row % 100000 == 0:
                _logger.info("row %s >>>>>>>>>>> %s >>>>>>>>>>" % (row, datetime.now()))
            source = line['source_location']
            dest = line['dest_location']
            if len(source.split('/')) > 2:
                line['source_location'] = source.split('/')[-2] + '/' + source.split('/')[-1]
            if len(dest.split('/')) > 2:
                line['dest_location'] = dest.split('/')[-2] + '/' + dest.split('/')[-1]

            if row % 1048576 == 0:
                count += 1
                ws = wb.add_worksheet('Stock Move %s' % count)
                self.set_paper(wb, ws)
                self.set_header(ws)
                row = 1

            ws.write(row, col, line['reference'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['source_document'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['product_category'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['product'], self.styles['normal'])
            col += 1
            # ws.write(row, col, line['unit_price'], self.styles['amount'])
            # col += 1
            ws.write(row, col, line['quantity'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['uom'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['source_location'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['dest_location'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['date'], self.styles['date_left'])
            col += 1
            ws.write(row, col, line['date_expected'], self.styles['date_left'])
            col += 1
            ws.write(row, col, line['status'], self.styles['normal'])

        _logger.info("END>>>>>>>>> ---> %s" % datetime.now())

    def where(self, report):

        def _in_condition(obj):
            ids = ['(%s)' % p.id for p in obj]
            ids_string = ", ".join(ids)
            return ids_string

        def cutoff_time(date):
            # Convert from GMT+8 to UTC, so that it match with database data time
            date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT) - timedelta(hours=8)
            return date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        wheres = {
            'start_date': cutoff_time(report.start_date + ' 00:00:00'),
            'end_date': cutoff_time(report.end_date + ' 23:59:59'),
            'product_ids': '',
            'location_ids': '',
            'location_dest_ids': '',
        }

        if not report.product_ids:
            products = self.get_product(report)
        else:
            product_tmpl_ids = report.product_ids.ids
            products = self.env['product.product'].search([('product_tmpl_id', 'in', product_tmpl_ids)])
        wheres['product_ids'] = _in_condition(products)

        all_locations = self.env['stock.location'].search([])

        if not report.location_ids:
            location_ids = all_locations
        else:
            location_ids = report.location_ids
        wheres['location_ids'] = _in_condition(location_ids)

        if not report.location_dest_ids:
            location_dest_ids = all_locations
        else:
            location_dest_ids = report.location_dest_ids
        wheres['location_dest_ids'] = _in_condition(location_dest_ids)

        if wheres['product_ids']:
            wheres['product_ids'] = "AND sm.product_id = ANY (VALUES %s)" % wheres['product_ids']
            wheres['location_ids'] = "AND sm.location_id = ANY (VALUES %s)" % wheres['location_ids']
            wheres['location_dest_ids'] = "AND sm.location_dest_id = ANY (VALUES %s)" % wheres['location_dest_ids']

        return wheres

    def get_product(self, report):
        products = []
        if report.product_categ_ids:
            product_ids = self.env['product.template'].search([('categ_id', 'child_of', [x.id for x in report.product_categ_ids])])
        else:
            product_ids = self.env['product.template'].search([])

        if product_ids:
            products = self.env['product.product'].search([('product_tmpl_id', 'in', product_ids.ids)])

        return products

br_stock_move_report('report.br_stock.br_stock_move_report', 'stock.move.report.wizard')



