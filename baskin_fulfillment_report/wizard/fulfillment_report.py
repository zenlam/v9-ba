# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
import xlsxwriter
from cStringIO import StringIO
from openerp.exceptions import Warning as UserError
from datetime import datetime, timedelta
import pytz
import base64
from openerp.tools.translate import _


DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
GROUP_BY = {
    'product_category': 'Product Category',
    'product': 'Product'
}


def convert_timezone(from_tz, to_tz, date):
    from_tz = pytz.timezone(from_tz).localize(datetime.strptime(date, DATE_FORMAT))
    to_tz = from_tz.astimezone(pytz.timezone(to_tz))
    return to_tz.strftime(DATE_FORMAT)


class FulfillmentReportShowBy(models.Model):
    _name = 'fulfillment.report.show.by'
    _description = 'Fulfillment Report Show By Selection'

    name = fields.Char(string='Selection Name')
    code = fields.Char(string='Selection Code')
    type = fields.Selection([('all', 'All'), ('internal', 'Internal'), ('supplier', 'Supplier'),
                             ('external', 'External')], string='Type')


class FulfillmentReport(models.TransientModel):
    _name = 'fulfillment.report'
    _description = 'Print Fulfillment Report'

    report_type = fields.Selection([('internal', 'Internal'), ('supplier', 'Supplier'), ('external', 'External')],
                                   default='internal', string='Report Type')
    product_category_ids = fields.Many2many('product.category', 'fulfillment_product_category_rel', 'report_id',
                                            'category_id', string='Product Category')
    product_ids = fields.Many2many('product.product', 'fulfillment_product_rel', 'report_id', 'product_id',
                                   string='Product')
    show_by = fields.Many2one('fulfillment.report.show.by', string='Show By')
    show_by_code = fields.Char(related='show_by.code')
    group_by = fields.Selection([('product_category', 'Product Category'), ('product', 'Product')], string='Group By')
    uom_type = fields.Selection([('standard', 'Standard'), ('purchase', 'Purchase UoM'),
                                 ('distribution', 'Distribution'), ('storage', 'Storage')], default='standard', string='UOM')
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    source_warehouse_internal = fields.Many2many('stock.warehouse', 'fulfillment_internal_source_warehouse_rel',
                                                 'report_id', 'source_warehouse_id', string='Source Warehouse')
    source_warehouse_external = fields.Many2many('stock.warehouse', 'fulfillment_external_source_warehouse_rel',
                                                 'report_id', 'source_warehouse_id', string='Source Warehouse')
    dest_warehouse = fields.Many2many('stock.warehouse', 'fulfillment_dest_warehouse_rel', 'report_id',
                                      'dest_warehouse_id', string='Destination Warehouse')
    file_name = fields.Binary()

    @api.onchange('show_by')
    def onchange_show_by(self):
        if self.show_by_code != 'by_product':
            self.group_by = False

    @api.onchange('report_type')
    def onchange_report_type(self):
        self.show_by = self.source_warehouse_external = self.source_warehouse_internal = self.dest_warehouse = ''

    def _get_purchase_uom_table(self, args):
        purchase_uom_str = """
            SELECT
                purchase_pu.id    AS id,
                purchase_pu.name    AS name,
                pt.id               AS product_id,
                purchase_pu.factor  AS factor
            FROM product_product pp
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_supplierinfo ps ON ps.product_tmpl_id = pt.id
            LEFT JOIN product_uom purchase_pu ON purchase_pu.vendor_id = ps.id
            WHERE ps.is_default is True
            AND purchase_pu.is_po_default is True
            AND ps.company_id = '{company_id}'
            AND {sql_product_string}
            AND purchase_pu.active is True
            """.format(**args)
        return purchase_uom_str

    def _get_storage_uom_table(self, args):
        storage_uom_str = """
            SELECT
                storage_pu.id    AS id,
                storage_pu.name    AS name,
                pt.id              AS product_id,
                storage_pu.factor  AS factor
            FROM product_product pp
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_supplierinfo ps ON ps.product_tmpl_id = pt.id
            LEFT JOIN product_uom storage_pu ON storage_pu.vendor_id = ps.id
            WHERE ps.is_default is True
            AND storage_pu.is_storage is True
            AND ps.company_id = '{company_id}'
            AND {sql_product_string}
            AND storage_pu.active is True
        """.format(**args)
        return storage_uom_str

    def _get_distribute_uom_table(self, args):
        distribution_uom_str = """
           SELECT
               distribution_pu.id       AS id,
               distribution_pu.name    AS name,
               pt.id                    AS product_id,
               distribution_pu.factor   AS factor
           FROM product_product pp
           JOIN product_template pt ON pp.product_tmpl_id = pt.id
           JOIN product_supplierinfo ps ON ps.product_tmpl_id = pt.id
           LEFT JOIN product_uom distribution_pu ON distribution_pu.vendor_id = ps.id
           WHERE ps.is_default is True
           AND distribution_pu.is_distribution is True
           AND ps.company_id = '{company_id}'
           AND {sql_product_string}
           AND distribution_pu.active is True
        """.format(**args)
        return distribution_uom_str

    def get_internal_by_transaction(self, args):
        sql = '''
            WITH purchase_uom AS (
            %s
            ),
            storage_uom AS (
            %s
            ),
            distribution_uom AS (
            %s
            )
            SELECT
                bsrt.name              AS document_no,
                bsrt.date_order::timestamp::date        AS order_date,
                sw1.name               AS source_warehouse,
                sw2.name               AS destination_warehouse,
                pp.name_template       AS product,
                standard_pu.name       AS standard_uom_name,
                CASE WHEN purchase_pu.id is NOT NULL 
                    THEN purchase_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN purchase_pu_default.name
                    ELSE standard_pu.name
                END AS purchase_uom_name,
                CASE WHEN storage_pu.id is NOT NULL
                    THEN storage_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN storage_pu_default.name
                    ELSE standard_pu.name 
                END AS storage_uom_name,
                CASE WHEN distribution_pu.id is NOT NULL
                    THEN distribution_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN distribution_pu_default.name
                    ELSE standard_pu.name 
                END AS distribution_uom_name,
                (t1.ordered_qty/ordering_pu.factor) AS standard_order_qty,
                CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.ordered_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END AS purchase_order_qty,
                CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.ordered_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END AS storage_order_qty,
                CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.ordered_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END AS distribution_order_qty,
                (t1.committed_qty/ordering_pu.factor) AS standard_fulfill_qty,
                CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.committed_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END AS purchase_fulfill_qty,
                CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.committed_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END AS storage_fulfill_qty,
                CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.committed_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END AS distribution_fulfill_qty,
                (t1.dispute_qty/ordering_pu.factor) AS standard_dispute_qty,
                CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.dispute_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END AS purchase_dispute_qty,
                CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.dispute_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END AS storage_dispute_qty,
                CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.dispute_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END AS distribution_dispute_qty
            FROM br_stock_request_transfer_line t1
            JOIN br_stock_request_transfer bsrt ON t1.transfer_id = bsrt.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN stock_warehouse sw1 ON bsrt.warehouse_id = sw1.id
            JOIN stock_warehouse sw2 ON bsrt.dest_warehouse_id = sw2.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.uom_id
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN purchase_uom purchase_pu_default ON purchase_pu_default.product_id = pt.id
            LEFT JOIN storage_uom storage_pu_default ON storage_pu_default.product_id = pt.id
            LEFT JOIN distribution_uom distribution_pu_default ON distribution_pu_default.product_id = pt.id
            WHERE {sql_product_string}
            AND bsrt.date_order >= '{start_date}'
            AND bsrt.date_order <= '{end_date}'
            AND {sql_source_warehouse_string}
            AND {sql_destination_warehouse_string}
            AND bsrt.state not in ('cancelled', 'dropped', 'draft', 'done')
            ORDER BY bsrt.name, bsrt.date_order, pp.name_template
        '''.format(**args) % (self._get_purchase_uom_table(args), self._get_storage_uom_table(args),
                              self._get_distribute_uom_table(args))
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_internal_by_product_category(self, args):
        sql = '''
            WITH purchase_uom AS (
            %s
            ),
            storage_uom AS (
            %s
            ),
            distribution_uom AS (
            %s
            )
            SELECT 
                pc.complete_name            AS product_category,
                sum(t1.ordered_qty/ordering_pu.factor) AS standard_order_qty,                
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END) AS purchase_order_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END) AS storage_order_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END) AS distribution_order_qty,
                sum(t1.committed_qty/ordering_pu.factor) AS standard_fulfill_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END) AS purchase_fulfill_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END) AS storage_fulfill_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END) AS distribution_fulfill_qty,
                sum(t1.dispute_qty/ordering_pu.factor) AS standard_dispute_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END) AS purchase_dispute_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END) AS storage_dispute_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END) AS distribution_dispute_qty
            FROM br_stock_request_transfer_line t1
            JOIN br_stock_request_transfer bsrt ON t1.transfer_id = bsrt.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            JOIN stock_warehouse sw1 ON bsrt.warehouse_id = sw1.id
            JOIN stock_warehouse sw2 ON bsrt.dest_warehouse_id = sw2.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.uom_id
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN purchase_uom purchase_pu_default ON purchase_pu_default.product_id = pt.id
            LEFT JOIN storage_uom storage_pu_default ON storage_pu_default.product_id = pt.id
            LEFT JOIN distribution_uom distribution_pu_default ON distribution_pu_default.product_id = pt.id
            WHERE {sql_product_string}
            AND bsrt.date_order >= '{start_date}'
            AND bsrt.date_order <= '{end_date}'
            AND {sql_source_warehouse_string}
            AND {sql_destination_warehouse_string}
            AND bsrt.state not in ('cancelled', 'dropped', 'draft', 'done')
            GROUP BY pc.complete_name
            ORDER BY pc.complete_name
        '''.format(**args) % (self._get_purchase_uom_table(args), self._get_storage_uom_table(args),
                              self._get_distribute_uom_table(args))
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_internal_by_product(self, args):
        sql = '''
            WITH purchase_uom AS (
            %s
            ),
            storage_uom AS (
            %s
            ),
            distribution_uom AS (
            %s
            )
            SELECT 
                pc.complete_name            AS product_category,
                pp.name_template            AS product,
                sum(t1.ordered_qty/ordering_pu.factor) AS standard_order_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END) AS purchase_order_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END) AS storage_order_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.ordered_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.ordered_qty/ordering_pu.factor)
                END) AS distribution_order_qty,
                sum(t1.committed_qty/ordering_pu.factor) AS standard_fulfill_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END) AS purchase_fulfill_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END) AS storage_fulfill_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.committed_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.committed_qty/ordering_pu.factor)
                END) AS distribution_fulfill_qty,
                sum(t1.dispute_qty/ordering_pu.factor) AS standard_dispute_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END) AS purchase_dispute_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END) AS storage_dispute_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.dispute_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.dispute_qty/ordering_pu.factor)
                END) AS distribution_dispute_qty
            FROM br_stock_request_transfer_line t1
            JOIN br_stock_request_transfer bsrt ON t1.transfer_id = bsrt.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            JOIN stock_warehouse sw1 ON bsrt.warehouse_id = sw1.id
            JOIN stock_warehouse sw2 ON bsrt.dest_warehouse_id = sw2.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.uom_id
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN purchase_uom purchase_pu_default ON purchase_pu_default.product_id = pt.id
            LEFT JOIN storage_uom storage_pu_default ON storage_pu_default.product_id = pt.id
            LEFT JOIN distribution_uom distribution_pu_default ON distribution_pu_default.product_id = pt.id
            WHERE {sql_product_string}
            AND bsrt.date_order >= '{start_date}'
            AND bsrt.date_order <= '{end_date}'
            AND {sql_source_warehouse_string}
            AND {sql_destination_warehouse_string}
            AND bsrt.state not in ('cancelled', 'dropped', 'draft', 'done')
            GROUP BY pc.complete_name, pp.name_template
            ORDER BY pc.complete_name, pp.name_template
        '''.format(**args) % (self._get_purchase_uom_table(args), self._get_storage_uom_table(args),
                              self._get_distribute_uom_table(args))
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_supplier_by_transaction(self, args):
        sql = '''
            SELECT
                po.name              AS document_no,
                po.date_order::timestamp::date        AS order_date,
                sw2.name               AS destination_warehouse,
                pp.name_template       AS product,
                standard_pu.name       AS standard_uom_name,
                CASE WHEN purchase_pu.id is NOT NULL
                    THEN purchase_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_po.id is NOT NULL 
                    THEN purchase_pu_po.name
                    ELSE standard_pu.name 
                END AS purchase_uom_name,
                CASE WHEN storage_pu.id is NOT NULL
                    THEN storage_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_po.id is NOT NULL 
                    THEN storage_pu_po.name
                    ELSE standard_pu.name 
                END AS storage_uom_name,
                CASE WHEN distribution_pu.id is NOT NULL
                    THEN distribution_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_po.id is NOT NULL 
                    THEN distribution_pu_po.name
                    ELSE standard_pu.name 
                END AS distribution_uom_name,
                (t1.product_qty/ordering_pu.factor) AS standard_order_qty,
                CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * purchase_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END AS purchase_order_qty,
                CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * storage_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END AS storage_order_qty,
                CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * distribution_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END AS distribution_order_qty,
                (t1.qty_received/ordering_pu.factor) AS standard_fulfill_qty,
                CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * purchase_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END AS purchase_fulfill_qty,
                CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * storage_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END AS storage_fulfill_qty,
                CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * distribution_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END AS distribution_fulfill_qty
            FROM purchase_order_line t1
            JOIN purchase_order po ON t1.order_id = po.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN stock_picking_type spt ON po.picking_type_id = spt.id
            JOIN stock_warehouse sw2 ON spt.warehouse_id = sw2.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.product_uom
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN product_supplierinfo supplier_po ON (supplier_po.name = po.partner_id AND supplier_po.product_tmpl_id = pt.id) 
            LEFT JOIN product_uom purchase_pu_po ON (purchase_pu_po.product_tmpl_id = pt.id AND purchase_pu_po.vendor_id = supplier_po.id AND purchase_pu_po.is_po_default is True and purchase_pu_po.active is True)
            LEFT JOIN product_uom storage_pu_po ON (storage_pu_po.product_tmpl_id = pt.id AND storage_pu_po.vendor_id = supplier_po.id AND storage_pu_po.is_storage is True and storage_pu_po.active is True)
            LEFT JOIN product_uom distribution_pu_po ON (distribution_pu_po.product_tmpl_id = pt.id AND distribution_pu_po.vendor_id = supplier_po.id AND distribution_pu_po.is_distribution is True and distribution_pu_po.active is True)
            WHERE {sql_product_string}
            AND po.date_order >= '{start_date}'
            AND po.date_order <= '{end_date}'
            AND {sql_destination_warehouse_string}
            AND po.state in ('purchase')
            ORDER BY po.name, po.date_order, pp.name_template
        '''.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_supplier_by_product_category(self, args):
        sql = '''
            SELECT
                pc.complete_name            AS product_category,
                sum(t1.product_qty/ordering_pu.factor) AS standard_order_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * purchase_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END) AS purchase_order_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * storage_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END) AS storage_order_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * distribution_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END) AS distribution_order_qty,
                sum(t1.qty_received/ordering_pu.factor) AS standard_fulfill_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * purchase_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END) AS purchase_fulfill_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * storage_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END) AS storage_fulfill_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * distribution_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END) AS distribution_fulfill_qty
            FROM purchase_order_line t1
            JOIN purchase_order po ON t1.order_id = po.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN stock_picking_type spt ON po.picking_type_id = spt.id
            JOIN stock_warehouse sw2 ON spt.warehouse_id = sw2.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.product_uom
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN product_supplierinfo supplier_po ON (supplier_po.name = po.partner_id AND supplier_po.product_tmpl_id = pt.id) 
            LEFT JOIN product_uom purchase_pu_po ON (purchase_pu_po.product_tmpl_id = pt.id AND purchase_pu_po.vendor_id = supplier_po.id AND purchase_pu_po.is_po_default is True and purchase_pu_po.active is True)
            LEFT JOIN product_uom storage_pu_po ON (storage_pu_po.product_tmpl_id = pt.id AND storage_pu_po.vendor_id = supplier_po.id AND storage_pu_po.is_storage is True and storage_pu_po.active is True)
            LEFT JOIN product_uom distribution_pu_po ON (distribution_pu_po.product_tmpl_id = pt.id AND distribution_pu_po.vendor_id = supplier_po.id AND distribution_pu_po.is_distribution is True and distribution_pu_po.active is True)
            WHERE {sql_product_string}
            AND po.date_order >= '{start_date}'
            AND po.date_order <= '{end_date}'
            AND {sql_destination_warehouse_string}
            AND po.state in ('purchase')
            GROUP BY pc.complete_name
            ORDER BY pc.complete_name
        '''.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_supplier_by_product(self, args):
        sql = '''
            SELECT
                pc.complete_name            AS product_category,
                pp.name_template            AS product,
                sum(t1.product_qty/ordering_pu.factor) AS standard_order_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * purchase_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END) AS purchase_order_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * storage_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END) AS storage_order_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.product_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_po.id is NOT NULL 
                    THEN (t1.product_qty/ordering_pu.factor) * distribution_pu_po.factor
                    ELSE (t1.product_qty/ordering_pu.factor)
                END) AS distribution_order_qty,
                sum(t1.qty_received/ordering_pu.factor) AS standard_fulfill_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * purchase_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END) AS purchase_fulfill_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * storage_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END) AS storage_fulfill_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL
                    THEN (t1.qty_received/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_po.id is NOT NULL 
                    THEN (t1.qty_received/ordering_pu.factor) * distribution_pu_po.factor
                    ELSE (t1.qty_received/ordering_pu.factor)
                END) AS distribution_fulfill_qty
            FROM purchase_order_line t1
            JOIN purchase_order po ON t1.order_id = po.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN stock_picking_type spt ON po.picking_type_id = spt.id
            JOIN stock_warehouse sw2 ON spt.warehouse_id = sw2.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.product_uom
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN product_supplierinfo supplier_po ON (supplier_po.name = po.partner_id AND supplier_po.product_tmpl_id = pt.id) 
            LEFT JOIN product_uom purchase_pu_po ON (purchase_pu_po.product_tmpl_id = pt.id AND purchase_pu_po.vendor_id = supplier_po.id AND purchase_pu_po.is_po_default is True and purchase_pu_po.active is True)
            LEFT JOIN product_uom storage_pu_po ON (storage_pu_po.product_tmpl_id = pt.id AND storage_pu_po.vendor_id = supplier_po.id AND storage_pu_po.is_storage is True and storage_pu_po.active is True)
            LEFT JOIN product_uom distribution_pu_po ON (distribution_pu_po.product_tmpl_id = pt.id AND distribution_pu_po.vendor_id = supplier_po.id AND distribution_pu_po.is_distribution is True and distribution_pu_po.active is True)
            WHERE {sql_product_string}
            AND po.date_order >= '{start_date}'
            AND po.date_order <= '{end_date}'
            AND {sql_destination_warehouse_string}
            AND po.state in ('purchase')
            GROUP BY pc.complete_name, pp.name_template
            ORDER BY pc.complete_name, pp.name_template
        '''.format(**args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_external_by_transaction(self, args):
        sql = '''
            WITH purchase_uom AS (
            %s
            ),
            storage_uom AS (
            %s
            ),
            distribution_uom AS (
            %s
            )
            SELECT
                so.name              AS document_no,
                so.date_order::timestamp::date        AS order_date,
                sw1.name               AS source_warehouse,
                pp.name_template       AS product,
                standard_pu.name       AS standard_uom_name,
                CASE WHEN purchase_pu.id is NOT NULL 
                    THEN purchase_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN purchase_pu_default.name
                    ELSE standard_pu.name
                END AS purchase_uom_name,
                CASE WHEN storage_pu.id is NOT NULL
                    THEN storage_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN storage_pu_default.name
                    ELSE standard_pu.name 
                END AS storage_uom_name,
                CASE WHEN distribution_pu.id is NOT NULL
                    THEN distribution_pu.name
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN distribution_pu_default.name
                    ELSE standard_pu.name 
                END AS distribution_uom_name,
                (t1.product_uom_qty/ordering_pu.factor) AS standard_order_qty,
                CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END AS purchase_order_qty,
                CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END AS storage_order_qty,
                CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END AS distribution_order_qty,
                (t1.qty_delivered/ordering_pu.factor) AS standard_fulfill_qty,
                CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END AS purchase_fulfill_qty,
                CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END AS storage_fulfill_qty,
                CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END AS distribution_fulfill_qty
            FROM sale_order_line t1
            JOIN sale_order so ON t1.order_id = so.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN stock_warehouse sw1 ON so.warehouse_id = sw1.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.product_uom
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN purchase_uom purchase_pu_default ON purchase_pu_default.product_id = pt.id
            LEFT JOIN storage_uom storage_pu_default ON storage_pu_default.product_id = pt.id
            LEFT JOIN distribution_uom distribution_pu_default ON distribution_pu_default.product_id = pt.id
            WHERE {sql_product_string}
            AND so.date_order >= '{start_date}'
            AND so.date_order <= '{end_date}'
            AND {sql_source_warehouse_string}
            AND so.state in ('sale')
            ORDER BY so.name, so.date_order, pp.name_template
        '''.format(**args) % (self._get_purchase_uom_table(args), self._get_storage_uom_table(args),
                              self._get_distribute_uom_table(args))
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_external_by_product_category(self, args):
        sql = '''
            WITH purchase_uom AS (
            %s
            ),
            storage_uom AS (
            %s
            ),
            distribution_uom AS (
            %s
            )
            SELECT
                pc.complete_name            AS product_category,
                sum(t1.product_uom_qty/ordering_pu.factor) AS standard_order_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END) AS purchase_order_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END) AS storage_order_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END) AS distribution_order_qty,
                sum(t1.qty_delivered/ordering_pu.factor) AS standard_fulfill_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END) AS purchase_fulfill_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END) AS storage_fulfill_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END) AS distribution_fulfill_qty
            FROM sale_order_line t1
            JOIN sale_order so ON t1.order_id = so.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN stock_warehouse sw1 ON so.warehouse_id = sw1.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.product_uom
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN purchase_uom purchase_pu_default ON purchase_pu_default.product_id = pt.id
            LEFT JOIN storage_uom storage_pu_default ON storage_pu_default.product_id = pt.id
            LEFT JOIN distribution_uom distribution_pu_default ON distribution_pu_default.product_id = pt.id
            WHERE {sql_product_string}
            AND so.date_order >= '{start_date}'
            AND so.date_order <= '{end_date}'
            AND {sql_source_warehouse_string}
            AND so.state in ('sale')
            GROUP BY pc.complete_name
            ORDER BY pc.complete_name
        '''.format(**args) % (self._get_purchase_uom_table(args), self._get_storage_uom_table(args),
                              self._get_distribute_uom_table(args))
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_external_by_product(self, args):
        sql = '''
            WITH purchase_uom AS (
            %s
            ),
            storage_uom AS (
            %s
            ),
            distribution_uom AS (
            %s
            )
            SELECT
                pc.complete_name            AS product_category,
                pp.name_template            AS product,
                sum(t1.product_uom_qty/ordering_pu.factor) AS standard_order_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END) AS purchase_order_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END) AS storage_order_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.product_uom_qty/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.product_uom_qty/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.product_uom_qty/ordering_pu.factor)
                END) AS distribution_order_qty,
                sum(t1.qty_delivered/ordering_pu.factor) AS standard_fulfill_qty,
                SUM(CASE WHEN purchase_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * purchase_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND purchase_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * purchase_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END) AS purchase_fulfill_qty,
                SUM(CASE WHEN storage_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * storage_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND storage_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * storage_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END) AS storage_fulfill_qty,
                SUM(CASE WHEN distribution_pu.id is NOT NULL 
                    THEN (t1.qty_delivered/ordering_pu.factor) * distribution_pu.factor
                    WHEN ordering_pu.vendor_id is NULL AND distribution_pu_default.id is NOT NULL
                    THEN (t1.qty_delivered/ordering_pu.factor) * distribution_pu_default.factor
                    ELSE (t1.qty_delivered/ordering_pu.factor)
                END) AS distribution_fulfill_qty
            FROM sale_order_line t1
            JOIN sale_order so ON t1.order_id = so.id
            JOIN product_product pp ON t1.product_id = pp.id
            JOIN stock_warehouse sw1 ON so.warehouse_id = sw1.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_category pc ON pt.categ_id = pc.id
            JOIN product_uom ordering_pu ON ordering_pu.id = t1.product_uom
            LEFT JOIN product_uom standard_pu ON (standard_pu.category_id = ordering_pu.category_id AND standard_pu.uom_type = 'reference' AND standard_pu.active is True)
            LEFT JOIN product_uom purchase_pu ON (purchase_pu.product_tmpl_id = pt.id AND purchase_pu.vendor_id = ordering_pu.vendor_id AND purchase_pu.is_po_default is True AND purchase_pu.active is True)
            LEFT JOIN product_uom storage_pu ON (storage_pu.product_tmpl_id = pt.id AND storage_pu.vendor_id = ordering_pu.vendor_id AND storage_pu.is_storage is True AND storage_pu.active is True)
            LEFT JOIN product_uom distribution_pu ON (distribution_pu.product_tmpl_id = pt.id AND distribution_pu.vendor_id = ordering_pu.vendor_id AND distribution_pu.is_distribution is True AND distribution_pu.active is True)
            LEFT JOIN purchase_uom purchase_pu_default ON purchase_pu_default.product_id = pt.id
            LEFT JOIN storage_uom storage_pu_default ON storage_pu_default.product_id = pt.id
            LEFT JOIN distribution_uom distribution_pu_default ON distribution_pu_default.product_id = pt.id
            WHERE {sql_product_string}
            AND so.date_order >= '{start_date}'
            AND so.date_order <= '{end_date}'
            AND {sql_source_warehouse_string}
            AND so.state in ('sale')
            GROUP BY pc.complete_name, pp.name_template
            ORDER BY pc.complete_name, pp.name_template
        '''.format(**args) % (self._get_purchase_uom_table(args), self._get_storage_uom_table(args),
                              self._get_distribute_uom_table(args))
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_data(self, parameter):
        if self.report_type == 'internal':
            if self.show_by_code == 'by_product':
                if self.group_by == 'product':
                    return self.get_internal_by_product(parameter)
                return self.get_internal_by_product_category(parameter)
            return self.get_internal_by_transaction(parameter)
        elif self.report_type == 'supplier':
            if self.show_by_code == 'by_product':
                if self.group_by == 'product':
                    return self.get_supplier_by_product(parameter)
                return self.get_supplier_by_product_category(parameter)
            return self.get_supplier_by_transaction(parameter)
        elif self.report_type == 'external':
            if self.show_by_code == 'by_product':
                if self.group_by == 'product':
                    return self.get_external_by_product(parameter)
                return self.get_external_by_product_category(parameter)
            return self.get_external_by_transaction(parameter)

    @api.multi
    def action_print(self):
        self.ensure_one()
        fp = StringIO()
        workbook = xlsxwriter.Workbook(fp)
        #################################################################################
        top_style = workbook.add_format({'bold': 1, 'valign': 'vcenter', 'align': 'center'})
        top_style.set_font_name('Arial')
        top_style.set_font_size('20')
        top_style.set_text_wrap()
        #################################################################################
        header_style = workbook.add_format({'align': 'left', 'valign': 'vcenter'})
        header_style.set_font_name('Arial')
        header_style.set_font_size('11')
        header_style.set_text_wrap()
        #################################################################################
        header_style_right = workbook.add_format({'align': 'right', 'valign': 'vcenter'})
        header_style_right.set_font_name('Arial')
        header_style_right.set_font_size('11')
        header_style_right.set_text_wrap()
        #################################################################################
        header_style1 = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
        header_style1.set_font_name('Arial')
        header_style1.set_font_size('11')
        header_style1.set_border()
        header_style1.set_text_wrap()
        header_style1.set_bg_color('#D3D3D3')
        #################################################################################
        header_style2 = workbook.add_format({'bold': 1, 'align': 'center', 'valign': 'vcenter'})
        header_style2.set_font_name('Arial')
        header_style2.set_font_size('11')
        header_style2.set_border()
        header_style2.set_text_wrap()
        header_style2.set_bg_color('#00FFFF')
        #################################################################################
        header_style_float = workbook.add_format({'bold': 1, 'align': 'right', 'valign': 'vcenter'})
        header_style_float.set_font_name('Arial')
        header_style_float.set_font_size('12')
        header_style_float.set_border()
        header_style_float.set_text_wrap()
        header_style_float.set_num_format('#,##0.00;-#,##0.00')
        #################################################################################
        product_style = workbook.add_format({'valign': 'vcenter', 'bold': 1})
        product_style.set_text_wrap()
        product_style.set_font_name('Arial')
        product_style.set_font_size('12')
        #################################################################################
        normal_style = workbook.add_format({'valign': 'vcenter', 'align': 'left'})
        normal_style.set_border()
        normal_style.set_text_wrap()
        normal_style.set_font_name('Arial')
        normal_style.set_font_size('11')
        #################################################################################
        normal_center = workbook.add_format({'valign': 'vcenter', 'align': 'left'})
        normal_center.set_border()
        normal_center.set_text_wrap()
        normal_center.set_font_name('Arial')
        normal_center.set_font_size('11')
        #################################################################################
        normal_float = workbook.add_format({'valign': 'left', 'align': 'left'})
        normal_float.set_border()
        normal_float.set_text_wrap()
        normal_float.set_num_format('#,##0.00;-#,##0.00')
        normal_float.set_font_name('Arial')
        normal_float.set_font_size('11')
        #################################################################################
        normal_date = workbook.add_format({'valign': 'vcenter', 'align': 'left'})
        normal_date.set_border()
        normal_date.set_text_wrap()
        normal_date.set_num_format('dd mmmm yyyy')
        normal_date.set_font_name('Arial')
        normal_date.set_font_size('11')
        #################################################################################
        header_style_border = workbook.add_format({'bold': 1, 'align': 'left', 'valign': 'center'})
        header_style_border.set_font_name('Arial')
        header_style_border.set_font_size('12')
        header_style_border.set_border()
        header_style_border.set_text_wrap()
        ######################################################
        normal_style_right = workbook.add_format({'valign': 'right', 'align': 'right'})
        normal_style_right.set_border()
        normal_style_right.set_text_wrap()
        normal_style_right.set_font_name('Arial')
        normal_style_right.set_font_size('11')
        # ========================================================
        normal_float_right = workbook.add_format({'valign': 'right', 'align': 'right'})
        normal_float_right.set_border()
        normal_float_right.set_text_wrap()
        normal_float_right.set_num_format('#,##0.00;-#,##0.00')
        normal_float_right.set_font_name('Arial')
        normal_float_right.set_font_size('11')

        # ===========
        column_grey_style = workbook.add_format({'bold': 1, 'align': 'right', 'valign': 'vcenter'})
        column_grey_style.set_font_name('Arial')
        column_grey_style.set_font_size('11')
        column_grey_style.set_border()
        column_grey_style.set_text_wrap()
        column_grey_style.set_bg_color('#CFCBCA')
        column_grey_style.set_border(3)

        stock_location_obj = self.env['stock.location']
        product_product_obj = self.env['product.product']
        product_category_obj = self.env['product.category']

        if not self.report_type:
            raise UserError(_('Report type should not be empty.'))
        elif self.report_type == 'internal':
            filename = 'Fulfillment_Report_Internal'
        elif self.report_type == 'supplier':
            filename = 'Fulfillment_Report_Supplier'
        else:
            filename = 'Fulfillment_Report_External'
        worksheet = workbook.add_worksheet('Fulfillment Report')

        source_warehouses = []
        source_locations = []
        if self.report_type == 'internal':
            for source in self.source_warehouse_internal:
                source_warehouses.append(source.name)
                source_stock_location = stock_location_obj.search([('location_id', '=', source.view_location_id.id),
                                                                   ('is_stock_location', '=', True)])
                source_locations.append('/'.join(source_stock_location.complete_name.split('/')[1:]))
        elif self.report_type == 'external':
            for source in self.source_warehouse_external:
                source_warehouses.append(source.name)
                source_stock_location = stock_location_obj.search([('location_id', '=', source.view_location_id.id),
                                                                   ('is_stock_location', '=', True)])
                # raise warning if the source warehouse does not have a stock
                # location
                if not source_stock_location:
                    raise UserError(_(
                        '%s does not have a stock location.') % source.name)
                source_locations.append('/'.join(source_stock_location.complete_name.split('/')[1:]))

        dest_warehouses = []
        dest_locations = []
        for destination in self.dest_warehouse:
            dest_warehouses.append(destination.name)
            dest_stock_location = stock_location_obj.search([('location_id', '=', destination.view_location_id.id),
                                                             ('is_stock_location', '=', True)])
            # raise warning if the destination warehouse/outlet does not have
            # a stock location
            if not dest_stock_location:
                raise UserError(_('%s does not have a stock location.') % destination.name)
            dest_locations.append('/'.join(dest_stock_location.complete_name.split('/')[1:]))

        # check overlap warehouse in both source_warehouse and destination
        # warehouse
        overlap_warehouse = []
        for warehouse in self.dest_warehouse:
            if warehouse.id in self.source_warehouse_external.ids + \
                    self.source_warehouse_internal.ids:
                overlap_warehouse.append(warehouse.name)

        # raise warning if the an overlap warehouse is found
        if overlap_warehouse:
            raise UserError(_('You are not allowed to select the same '
                              'warehouse for both Source Warehouse and '
                              'Destination Outlet/Warehouse:\n %s') %
                            '\n'.join(overlap_warehouse))

        full_product_categories = []
        product_categories = []
        product_products = []
        if self.product_category_ids and self.product_ids:
            for categ in self.product_category_ids:
                product_categories.append(categ)
            for product in self.product_ids:
                product_products.append(product)
        elif self.product_category_ids and not self.product_ids:
            full_product_categories.extend(self.product_category_ids)
            for categ in self.product_category_ids:
                child_category = product_category_obj.search([('id', 'child_of', categ.id)])
                full_product_categories.extend(child_category)
                product_categories.append(categ)
            for category in full_product_categories:
                product_product = product_product_obj.search([('categ_id', '=', category.id)])
                for product in product_product:
                    product_products.append(product)
        elif not self.product_category_ids and self.product_ids:
            for product in self.product_ids:
                product_products.append(product)
        else:
            product_products = product_product_obj.search([('type', '!=', 'service')])

        if not self.product_category_ids and not self.product_ids:
            product_categ_str = ['All']
            product_str = ['All']
        else:
            product_categ_str = [categ.complete_name for categ in product_categories if product_categories]
            product_str = [prod.name_template for prod in product_products if product_products]

        start_date = self.start_date + ' 00:00:00'
        utc_start_date = convert_timezone(self.env.user.tz, 'UTC', start_date)

        end_date = self.end_date + ' 00:00:00'
        end_date = datetime.strptime(end_date, DATE_FORMAT) + timedelta(days=1)
        end_date = end_date.strftime(DATE_FORMAT)
        utc_end_date = convert_timezone(self.env.user.tz, 'UTC', end_date)

        worksheet.set_paper(9)
        worksheet.set_landscape()
        worksheet.set_margins(0.5, 0.3, 0.5, 0.5)
        worksheet.set_column(0, 10, 20)

        # report header
        col = 0
        worksheet.write(0, col, 'Fulfillment Report', header_style)
        worksheet.write(1, col, 'Report Show By', header_style)
        worksheet.write(2, col, 'Start Date', header_style)
        worksheet.write(3, col, 'End Date', header_style)
        worksheet.write(5, col, 'Source Warehouse', header_style)
        worksheet.write(6, col, 'Source Location', header_style)
        worksheet.write(7, col, 'Destination Outlet', header_style)
        worksheet.write(8, col, 'Destination Location', header_style)
        worksheet.write(10, col, 'Product Category', header_style)
        worksheet.write(11, col, 'Product', header_style)
        worksheet.write(12, col, 'UOM', header_style)

        row = 14

        if self.show_by_code == 'by_product':
            worksheet.write(13, col, 'Group By', header_style)
            row += 1
            col = 0
            if self.group_by == 'product_category':
                worksheet.write(row, col, 'Product Category', header_style1)
                col += 1
            elif self.group_by == 'product':
                worksheet.write(row, col, 'Product Category', header_style1)
                col += 1
                worksheet.write(row, col, 'Product', header_style1)
                col += 1
            worksheet.write(row, col, 'Order Qty', header_style1)
            col += 1
            worksheet.write(row, col, 'Fulfilled Qty', header_style1)
            col += 1
            if self.report_type == 'internal':
                worksheet.write(row, col, 'Dispute Qty', header_style1)
                col += 1
                worksheet.write(row, col, 'Final Fulfilled Qty', header_style1)
                col += 1
            worksheet.write(row, col, 'Variance', header_style1)
        else:
            r_type = self.report_type
            col = 0
            worksheet.write(row, col, 'Request No.' if r_type == 'internal' else 'PO No.' if r_type == 'supplier' else 'SO No.', header_style1)
            col += 1
            worksheet.write(row, col, 'Order Date', header_style1)
            col += 1
            if self.report_type == 'internal':
                worksheet.write(row, col, 'Warehouse', header_style1)
                col += 1
                worksheet.write(row, col, 'Outlet', header_style1)
                col += 1
            elif self.report_type == 'supplier':
                worksheet.write(row, col, 'To Warehouse/ Outlet', header_style1)
                col += 1
            else:
                worksheet.write(row, col, 'From Warehouse/ Outlet', header_style1)
                col += 1
            worksheet.write(row, col, 'Product', header_style1)
            col += 1
            worksheet.write(row, col, 'UOM', header_style1)
            col += 1
            worksheet.write(row, col, 'Order Qty', header_style1)
            col += 1
            worksheet.write(row, col, 'Fulfilled Qty', header_style1)
            col += 1
            if self.report_type == 'internal':
                worksheet.write(row, col, 'Dispute Qty', header_style1)
                col += 1
                worksheet.write(row, col, 'Final Fulfilled Qty', header_style1)
                col += 1
            worksheet.write(row, col, 'Variance', header_style1)
        # end of report header

        # report data
        col = 1
        worksheet.write(0, col, self.report_type.title(), header_style_right)
        worksheet.write(1, col, self.show_by.name, header_style_right)
        worksheet.write(2, col, self.start_date, header_style_right)
        worksheet.write(3, col, self.end_date, header_style_right)
        worksheet.write(5, col, ','.join(source_warehouses), header_style)
        worksheet.write(6, col, ','.join(source_locations), header_style)
        worksheet.write(7, col, ','.join(dest_warehouses), header_style)
        worksheet.write(8, col, ','.join(dest_locations), header_style)
        worksheet.write(10, col, ','.join(product_categ_str), header_style)
        worksheet.write(11, col, ','.join(product_str), header_style)
        worksheet.write(12, col, self.uom_type.title(), header_style)

        row = 15
        if product_products:
            product_list = [prod.id for prod in product_products if prod.type != 'service']
            if product_list:
                sql_product_string = 'pp.id in ' + str(product_list).replace('[', '(').replace(']', ')')
            else:
                sql_product_string = '1=0'
        else:
            sql_product_string = '1=0'

        sql_source_warehouse_string = '1=1'
        if self.report_type == 'internal' and self.source_warehouse_internal:
            source_warehouse_list = [warehouse.id for warehouse in self.source_warehouse_internal]
            sql_source_warehouse_string = 'sw1.id in ' + str(source_warehouse_list).replace('[', '(').replace(']', ')')
        elif self.report_type == 'external' and self.source_warehouse_external:
            source_warehouse_list = [warehouse.id for warehouse in self.source_warehouse_external]
            sql_source_warehouse_string = 'sw1.id in ' + str(source_warehouse_list).replace('[', '(').replace(']', ')')

        sql_destination_warehouse_string = '1=1'
        if self.dest_warehouse:
            dest_warehouse_list = [warehouse.id for warehouse in self.dest_warehouse]
            sql_destination_warehouse_string = 'sw2.id in ' + str(dest_warehouse_list).replace('[', '(').replace(']',
                                                                                                                 ')')

        company = self.env.user.company_id

        parameter = {
            'sql_product_string': sql_product_string,
            'start_date': utc_start_date,
            'end_date': utc_end_date,
            'sql_source_warehouse_string': sql_source_warehouse_string,
            'sql_destination_warehouse_string': sql_destination_warehouse_string,
            'company_id': company.id
        }

        uom_name_str = 'uom_name'
        order_qty_str = 'order_qty'
        fulfill_qty_str = 'fulfill_qty'
        dispute_qty_str = 'dispute_qty'
        res = self.get_data(parameter)
        if self.show_by_code == 'by_product':
            worksheet.write(13, col, GROUP_BY[self.group_by], header_style)
            row += 1
            if self.group_by == 'product_category':
                for line in res:
                    col = 0
                    worksheet.write(row, col, line['product_category'], normal_style)
                    col += 1
                    order_qty = line[self.uom_type + '_' + order_qty_str] or line['standard_' + order_qty_str]
                    fulfill_qty = line[self.uom_type + '_' + fulfill_qty_str] or line['standard_' + fulfill_qty_str]
                    worksheet.write(row, col, order_qty, normal_float)
                    col += 1
                    worksheet.write(row, col, fulfill_qty, normal_float)
                    col += 1
                    if self.report_type == 'internal':
                        dispute_qty = line[self.uom_type + '_' + dispute_qty_str] or line['standard_' + dispute_qty_str]
                        worksheet.write(row, col, dispute_qty, normal_float)
                        col += 1
                        final_fulfilled_qty = (fulfill_qty or 0) + (dispute_qty or 0)
                        worksheet.write(row, col, final_fulfilled_qty, normal_float)
                        col += 1
                        worksheet.write(row, col, final_fulfilled_qty - order_qty, normal_float)
                        row += 1
                    else:
                        worksheet.write(row, col, fulfill_qty - order_qty, normal_float)
                        row += 1
            elif self.group_by == 'product':
                for line in res:
                    col = 0
                    worksheet.write(row, col, line['product_category'], normal_style)
                    col += 1
                    worksheet.write(row, col, line['product'], normal_style)
                    col += 1
                    order_qty = line[self.uom_type + '_' + order_qty_str] or line['standard_' + order_qty_str]
                    fulfill_qty = line[self.uom_type + '_' + fulfill_qty_str] or line['standard_' + fulfill_qty_str]

                    worksheet.write(row, col, order_qty, normal_float)
                    col += 1
                    worksheet.write(row, col, fulfill_qty, normal_float)
                    col += 1
                    if self.report_type == 'internal':
                        dispute_qty = line[self.uom_type + '_' + dispute_qty_str] or line['standard_' + dispute_qty_str]
                        worksheet.write(row, col, dispute_qty, normal_float)
                        col += 1
                        final_fulfilled_qty = (fulfill_qty or 0) + (dispute_qty or 0)
                        worksheet.write(row, col, final_fulfilled_qty, normal_float)
                        col += 1
                        worksheet.write(row, col, final_fulfilled_qty - order_qty, normal_float)
                        row += 1
                    else:
                        worksheet.write(row, col, fulfill_qty - order_qty, normal_float)
                        row += 1
        else:
            for line in res:
                col = 0
                worksheet.write(row, col, line['document_no'], normal_style)
                col += 1
                worksheet.write(row, col, line['order_date'], normal_style)
                col += 1
                if self.report_type == 'internal':
                    worksheet.write(row, col, line['source_warehouse'], normal_float)
                    col += 1
                    worksheet.write(row, col, line['destination_warehouse'], normal_float)
                    col += 1
                elif self.report_type == 'supplier':
                    worksheet.write(row, col, line['destination_warehouse'], normal_float)
                    col += 1
                else:
                    worksheet.write(row, col, line['source_warehouse'], normal_float)
                    col += 1
                worksheet.write(row, col, line['product'], normal_style)
                col += 1
                uom_name = line[self.uom_type + '_' + uom_name_str] or line['standard_' + uom_name_str]
                worksheet.write(row, col, uom_name, normal_style)
                col += 1
                order_qty = line[self.uom_type + '_' + order_qty_str] or line['standard_' + order_qty_str]
                fulfill_qty = line[self.uom_type + '_' + fulfill_qty_str] or line['standard_' + fulfill_qty_str]
                worksheet.write(row, col, order_qty, normal_float)
                col += 1
                worksheet.write(row, col, fulfill_qty, normal_float)
                col += 1
                if self.report_type == 'internal':
                    dispute_qty = line[self.uom_type + '_' + dispute_qty_str] or line['standard_' + dispute_qty_str]
                    worksheet.write(row, col, dispute_qty, normal_float)
                    col += 1
                    final_fulfilled_qty = (fulfill_qty or 0) + (dispute_qty or 0)
                    worksheet.write(row, col, final_fulfilled_qty, normal_float)
                    col += 1
                    worksheet.write(row, col, final_fulfilled_qty - order_qty, normal_float)
                    row += 1
                else:
                    worksheet.write(row, col, fulfill_qty - order_qty, normal_float)
                    row += 1
        # end of report data
        workbook.close()
        out = base64.encodestring(fp.getvalue())
        self.write({'file_name': out, 'name': filename})
        fp.close()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=fulfillment.report&field=file_name&id=%s&filename=%s.xls' % (
                self.id, filename),
            'target': 'self',
        }