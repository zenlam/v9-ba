from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT

from openerp import api, fields, models, exceptions, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from collections import OrderedDict
import xlsxwriter

import logging
_logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class SalesReportProductConso(models.TransientModel):
    _name = 'sales.report.product.conso'

    partner_ids = fields.Many2many('res.partner', string='Customer')
    team_ids = fields.Many2many('crm.team', string='Channel')
    region_ids = fields.Many2many('customer.region', string='Region')
    state_ids = fields.Many2many('res.country.state', string='State')
    area_ids = fields.Many2many('customer.area', string='Area')
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    product_categ_ids = fields.Many2many(string='Product Category', comodel_name='product.category')
    product_ids = fields.Many2many(string='Product', comodel_name='product.template')
    only_invoice = fields.Boolean(string='Only Invoice?', default=False)

    @api.constrains('start_date', 'end_date')
    def date_range(self):
        if self.start_date and self.end_date:
            if datetime.strptime(self.start_date, DEFAULT_SERVER_DATE_FORMAT) > datetime.strptime(self.end_date, DEFAULT_SERVER_DATE_FORMAT):
                raise exceptions.ValidationError(_('End date must be greater than start date !'))
            date_diff = relativedelta(datetime.strptime(self.end_date, DEFAULT_SERVER_DATE_FORMAT), datetime.strptime(self.start_date, DEFAULT_SERVER_DATE_FORMAT))
            if date_diff.months > 3 or (date_diff.months >= 3 and date_diff.days > 0):
                raise exceptions.ValidationError(_('Date range should be less than or equal to 3 months!'))


    @api.onchange('product_categ_ids')
    def onchange_product_categ_ids(self):
        res = {'domain': {'product_ids': []}}
        if self.product_categ_ids:
            res['domain']['product_ids'] = [('categ_id', 'child_of', [categ.id for categ in self.product_categ_ids])]
        return res

    @api.onchange('region_ids')
    def onchange_region(self):
        res = {'domain': {'state_ids': []}}
        if self.region_ids:
            res['domain']['state_ids'] = [('region_id', 'in', self.region_ids.ids)]
        return res

    @api.onchange('state_ids')
    def onchange_state(self):
        res = {'domain': {'area_ids': []}}
        if self.state_ids:
            res['domain']['area_ids'] = [('state_id', 'in', self.state_ids.ids)]
        return res

    @api.onchange('area_ids')
    def onchange_area(self):
        if self.area_ids:
            # res['domain']['partner_ids'] = [('area_id', 'in', self.area_ids.ids), ('is_mega_scoop', '!=', True)]
            return {'domain': {'partner_ids': [('area_id', 'in', self.area_ids.ids), ('is_mega_scoop', '!=', True)]}}
        else:
            return {'domain': {'partner_ids': [('is_mega_scoop', '!=', True)]}}


    @api.multi
    def action_print(self):
        return self.env['report'].get_action(self, 'br_sales_report_product_conso.sales_report_product_conso')

class sales_report_product_conso(ReportXlsx):
    _name = 'report.br_sales_report_product_conso.sales_report_product_conso'

    def generate_xlsx_report(self, wb, data, report):
        ws = wb.add_worksheet('Sales Report By Product Conso')
        self.set_paper(wb, ws)
        self.styles = self.get_report_styles(wb)
        self.set_header(ws, report)
        report_data = self.get_data(report)
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
        ws.set_column(0, 0, 12)
        ws.set_column(1, 1, 25)
        ws.set_column(2, 2, 35)
        ws.set_column(3, 3, 15)
        ws.set_column(4, 4, 20)
        ws.set_column(5, 5, 40)
        ws.set_column(6, 6, 30)
        ws.set_column(7, 9, 10)
        ws.set_column(10, 12, 15)
        ws.set_column(13, 13, 20)
        ws.set_column(14, 14, 25)

    def set_header(self, ws, report):
        ws.merge_range('A1:B1', 'By Product Consolidation', self.styles['bold'])
        # ws.write('A1', u'By Product', self.styles['bold'])

        ws.write('A2', u'Date', self.styles['table_header'])
        ws.write('B2', u'Order Ref/Invoice No', self.styles['table_header'])
        ws.write('C2', u'Customer', self.styles['table_header'])
        ws.write('D2', u'Analytical Account', self.styles['table_header'])
        ws.write('E2', u'Menu Name', self.styles['table_header'])
        ws.write('F2', u'Product', self.styles['table_header'])
        ws.write('G2', u'Product Category', self.styles['table_header'])
        ws.write('H2', u'Qty', self.styles['table_header'])
        ws.write('I2', u'UOM', self.styles['table_header'])
        ws.write('J2', u'Amount', self.styles['table_header'])
        ws.write('K2', u'Region', self.styles['table_header'])
        ws.write('L2', u'State', self.styles['table_header'])
        ws.write('M2', u'Area', self.styles['table_header'])
        ws.write('N2', u'Channel', self.styles['table_header'])
        ws.write('O2', u'Responsible', self.styles['table_header'])

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
            -- GET TRADE SALES SESSION 
            WITH trade_sales_session AS (
            SELECT id 
            FROM pos_session
            WHERE config_id in 
                (SELECT id 
                from pos_config
                where is_trade_sales = True)
            AND state = 'closed'
            -- GET TRADE SALES ORDER    
            ),trade_sales_order as (
                SELECT 
                    distinct(pos_statement_id) as order_id
                FROM account_bank_statement_line absl
                    JOIN pos_order po on po.id = absl.pos_statement_id
                WHERE 
                    journal_id IN 
                    (SELECT id
                    FROM account_journal
                    WHERE is_trade_sales = True
                    )
                AND po.date_order BETWEEN '{start_date}' AND '{end_date}'
                AND po.state = 'done'
            ), order_details AS (
                SELECT 
                    po.id as order_id,
                    po.date_order as order_date,
                    po.name as reference
                FROM pos_order po
                WHERE 
                    po.session_id IN 
                    (SELECT id 
                    FROM trade_sales_session
                    )
                AND po.date_order BETWEEN '{start_date}' AND '{end_date}'
                AND po.state = 'done'
                UNION
                SELECT 
                    po.id as order_id,
                    po.date_order as order_date,
                    po.name as reference
                FROM pos_order po
                WHERE 
                    po.id IN 
                    (SELECT order_id 
                    FROM trade_sales_order
                    )
                AND po.date_order BETWEEN '{start_date}' AND '{end_date}'
            ),order_line AS (
                SELECT 
                    pol.order_id,
                    sum(pol.qty) as qty,
                    sum(pol.qty*pol.price_unit) as amount,
                    pp2.name_template as menu,
                    pp.name_template as product,
                    pc.name as product_category,
                    pt.uom_name as uom
                FROM pos_order po
                    INNER JOIN pos_order_line pol ON po.id = pol.order_id
                    INNER JOIN product_product pp ON pol.product_id = pp.id
                    INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    INNER JOIN product_category pc ON pt.categ_id = pc.id
                    INNER JOIN br_pos_order_line_master bpolm on pol.master_id = bpolm.id
                    INNER JOIN product_product pp2 on bpolm.product_id = pp2.id
                WHERE 
                    po.session_id IN 
                    (SELECT id 
                    FROM trade_sales_session
                    )
                AND po.date_order BETWEEN '{start_date}' AND '{end_date}'
                AND po.state = 'done'
                {pol_product_ids}
                GROUP BY 
                    pol.order_id,
                    pp2.name_template,
                    pp.name_template,
                    pc.name,
                    pt.uom_name
                UNION
                SELECT
                    pol.order_id,
                    sum(pol.qty) as qty,
                    sum(pol.qty*pol.price_unit) as amount,
                    pp2.name_template as menu,
                    pp.name_template as product,
                    pc.name as product_category,
                    pt.uom_name as uom
                FROM pos_order po
                    INNER JOIN pos_order_line pol ON po.id = pol.order_id
                    INNER JOIN product_product pp ON pol.product_id = pp.id
                    INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    INNER JOIN product_category pc ON pt.categ_id = pc.id
                    INNER JOIN br_pos_order_line_master bpolm on pol.master_id = bpolm.id
                    INNER JOIN product_product pp2 on bpolm.product_id = pp2.id
                WHERE 
                    po.id IN 
                    (SELECT order_id 
                    FROM trade_sales_order
                    )
                AND po.date_order BETWEEN '{start_date}' AND '{end_date}'
                {pol_product_ids}
                GROUP BY 
                pol.order_id,
                pp2.name_template,
                pp.name_template,
                pc.name,
                pt.uom_name
                )
        SELECT 
            date(order_details.order_date + INTERVAL '8 HOUR') as date,
            order_details.reference as reference,
            rp.name as customer,
            aac.name as analytic_account,
            order_line.menu as menu,
            order_line.product as product,
            order_line.product_category as product_category,
            order_line.qty as qty,
            order_line.uom as uom,
            order_line.amount as amount,
            cr.name as region,
            rcs.name as state,
            ca.name as area,
            null as Channel,
            rp2.name as responsible
        FROM pos_order po
            INNER JOIN br_multi_outlet_outlet bmoo ON po.outlet_id = bmoo.id
            INNER JOIN account_analytic_account aac ON bmoo.analytic_account_id = aac.id
            JOIN order_details ON po.id = order_details.order_id
            JOIN res_users ru ON po.user_id = ru.id
            LEFT JOIN res_partner rp ON po.partner_id = rp.id 
            JOIN res_partner rp2 ON ru.partner_id = rp2.id
            LEFT JOIN res_country_state rcs ON rp.state_id = rcs.id
            LEFT JOIN customer_region cr ON rcs.region_id = cr.id
            LEFT JOIN customer_area ca ON rp.area_id = ca.id
            JOIN order_line on po.id = order_line.order_id
        UNION
        SELECT
            ai.date_invoice as date,
            ai.move_name as reference,
            rp.name as Customer,
            aaa.name as Analytic_Account,
            null as menu,
            pp.name_template as Product,
            pc.name as Product_Category,
            sum(ail.quantity) as Qty,
            pt.uom_name as UOM,
            sum(ail.quantity*ail.price_unit) as Amount,
            cr.name as Region,
            rcs.name as State,
            ca.name as Area,
            ct.name as Channel,
            rp2.name as Responsible
        FROM account_invoice ai
            JOIN sale_order so ON ai.origin = so.name
            JOIN res_users ru ON ai.user_id = ru.id
            JOIN res_partner rp ON so.partner_id = rp.id
            JOIN res_partner rp2 ON ru.partner_id = rp2.id
            JOIN account_invoice_line ail ON ai.id = ail.invoice_id
            JOIN product_product pp ON ail.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            LEFT JOIN customer_area ca ON rp.area_id = ca.id
            JOIN res_country_state rcs ON rp.state_id = rcs.id
            LEFT JOIN customer_region cr ON rcs.region_id = cr.id
            JOIN crm_team ct ON ai.team_id = ct.id
            JOIN account_analytic_account aaa ON so.project_id = aaa.id
        WHERE ai.date_invoice between '{start_date}' AND '{end_date}'
        AND ai.state = 'paid'
        {channel_ids}
        {ail_product_ids}
        {ai_partner_ids}
        GROUP BY
            ai.date_invoice,
            ai.move_name,
            aaa.name,
            rp.name,
            pp.name_template,
            pc.name,
            pt.uom_name,
            cr.name,
            rcs.name,
            ca.name,
            ct.name,
            rp2.name
        ORDER BY
            reference
        """.format(**statements)

        query2 = """
        SELECT
            ai.date_invoice as date,
            ai.move_name as reference,
            rp.name as Customer,
            aaa.name as Analytic_Account,
            null as menu,
            pp.name_template as Product,
            pc.name as Product_Category,
            sum(ail.quantity) as Qty,
            pt.uom_name as UOM,
            sum(ail.quantity*ail.price_unit) as Amount,
            cr.name as Region,
            rcs.name as State,
            ca.name as Area,
            ct.name as Channel,
            rp2.name as Responsible
        FROM account_invoice ai
            JOIN sale_order so ON ai.origin = so.name
            JOIN res_users ru ON ai.user_id = ru.id
            JOIN res_partner rp ON so.partner_id = rp.id
            JOIN res_partner rp2 ON ru.partner_id = rp2.id
            JOIN account_invoice_line ail ON ai.id = ail.invoice_id
            JOIN product_product pp ON ail.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            LEFT JOIN customer_area ca ON rp.area_id = ca.id
            JOIN res_country_state rcs ON rp.state_id = rcs.id
            LEFT JOIN customer_region cr ON rcs.region_id = cr.id
            JOIN crm_team ct ON ai.team_id = ct.id
            JOIN account_analytic_account aaa ON so.project_id = aaa.id
        WHERE ai.date_invoice between '{start_date}' AND '{end_date}'
        AND ai.state = 'paid'
        {channel_ids}
        {ail_product_ids}
        {ai_partner_ids}
        GROUP BY
            ai.date_invoice,
            ai.move_name,
            aaa.name,
            rp.name,
            pp.name_template,
            pc.name,
            pt.uom_name,
            cr.name,
            rcs.name,
            ca.name,
            ct.name,
            rp2.name
        ORDER BY
            reference
        """.format(**statements)

        _logger.info("Q start time ---> %s" % datetime.now())
        if not report.only_invoice:
            self.env.cr.execute(query)
        else:
            self.env.cr.execute(query2)
        _logger.info("Q end time ---> %s" % datetime.now())
        raw_data = self.env.cr.dictfetchall()
        return raw_data

    def bind_data(self, ws, report_data, report):
        row = 1
        col = 0
        for line in report_data:
            row += 1
            col = 0

            ws.write(row, col, line['date'], self.styles['date_left'])
            col += 1
            ws.write(row, col, line['reference'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['customer'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['analytic_account'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['menu'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['product'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['product_category'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['qty'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['uom'], self.styles['normal'])
            col += 1
            ws.write(row, col, round(line['amount'], 2), self.styles['amount'])
            col += 1
            ws.write(row, col, line['region'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['state'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['area'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['channel'], self.styles['normal'])
            col += 1
            ws.write(row, col, line['responsible'], self.styles['normal'])

    # return 2 product and partner where clause query  ( pos and SO )
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
            'channel_ids': '',
            'product_ids': '',
            'partner_ids': '',
        }

        if not report.product_ids:
            products = self.get_product(report)
        else:
            product_tmpl_ids = report.product_ids.ids
            products = self.env['product.product'].search([('product_tmpl_id', 'in', product_tmpl_ids)])
        wheres['product_ids'] = _in_condition(products)

        if not report.team_ids:
            channels = self.get_channel(report)
        else:
            channels = report.team_ids
        wheres['channel_ids'] = _in_condition(channels)

        if not report.partner_ids:
            partners = self.get_customer(report)
        else:
            partners = report.partner_ids
        wheres['partner_ids'] = _in_condition(partners)

        if wheres['product_ids']:
            wheres['ail_product_ids'] = "AND ail.product_id = ANY (VALUES %s)" % wheres['product_ids']
            wheres['pol_product_ids'] = "AND pol.product_id = ANY (VALUES %s)" % wheres['product_ids']
        if wheres['channel_ids']:
            wheres['channel_ids'] = "AND ai.team_id = ANY (VALUES %s)" % wheres['channel_ids']
        if wheres['partner_ids']:
            wheres['ai_partner_ids'] = "AND ai.partner_id = ANY (VALUES %s)" % wheres['partner_ids']

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

    def get_channel(self, report):
        channel_ids = self.env['crm.team'].search([])

        return channel_ids

    ## will consider those customer without area_id,state_id
    def get_customer(self, report):
        partner_ids = []
        if report.area_ids:
            partner_ids = self.env['res.partner'].search([('area_id', 'in', report.area_ids.ids)])
        elif report.state_ids:
            partner_ids = self.env['res.partner'].search([('state_id', 'in', report.state_ids.ids)])
        elif report.region_ids:
            state_ids = self.env['res.country.state'].search([('region_id', 'in', report.region_ids.ids)])
            partner_ids = self.env['res.partner'].search([('state_id', 'in', state_ids.ids)])
        else:
            partner_ids = self.env['res.partner'].search([])

        if partner_ids:
            partner_ids = partner_ids.filtered(lambda x: not x.is_mega_scoop)

        return partner_ids

sales_report_product_conso('report.br_sales_report_product_conso.sales_report_product_conso', 'sales.report.product.conso')



