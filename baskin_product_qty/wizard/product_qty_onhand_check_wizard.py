# -*- coding: utf-8 -*-

from openerp import api, fields, models
from openerp.exceptions import UserError
from datetime import datetime
import pytz

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def convert_timezone(from_tz, to_tz, dt):
    from_tz = pytz.timezone(from_tz).localize(datetime.strptime(dt, DATETIME_FORMAT))
    to_tz = from_tz.astimezone(pytz.timezone(to_tz))
    return to_tz.strftime(DATETIME_FORMAT)


class ProductQtyOnhandCheckWizard(models.TransientModel):
    _name = 'product.qty.onhand.check.wizard'

    all_product_category = fields.Many2many('product.category', string='All Product Category',
                                            default=lambda self: self.env['product.category'].search([]), store=False)
    product_category_ids = fields.Many2many(
                            'product.category',
                            'category_product_qty_rel',
                            'product_qty_category_id',
                            'product_category_id',
                            string='Product Category')
    product_ids = fields.Many2many(
                        'product.product',
                        'product_product_qty_rel',
                        'product_qty_id',
                        'product_id',
                        string='Product')
    warehouse_ids = fields.Many2many(
                        'stock.warehouse',
                        'stock_warehouse_product_qty_rel',
                        'product_qty_warehouse_id',
                        'warehouse_id',
                        string='Warehouse')
    location_ids = fields.Many2many(
                        'stock.location',
                        'stock_location_product_qty_rel',
                        'product_qty_location_id',
                        'location_id',
                        string='Location',
                        domain=[('usage', '!=', 'view')])

    def get_distribution_uom(self, args):
        distribution_uom_str = """
           SELECT
               distribution.id       AS uom_id,
               pt.id                 AS product_id,
               ps.name               AS vendor_id,
               distribution.factor   AS factor
           FROM product_product pp
           JOIN product_template pt ON pp.product_tmpl_id = pt.id
           JOIN product_supplierinfo ps ON ps.product_tmpl_id = pt.id
           LEFT JOIN product_uom distribution ON distribution.vendor_id = ps.id
           WHERE distribution.is_distribution is True
           AND ps.is_default is True
           AND ps.company_id = '{company_id}'
           AND {sql_product_string}
        """.format(**args)
        return distribution_uom_str

    def get_stock_move_data(self, args):
        sql = """
        WITH distribution_uom AS (
            %s
        )
        SELECT
            distinct(sm.id),
            pp.id AS product_id,
            ps.name AS vendor_id,
            pt.uom_id           AS standard_uom,
            distribution.uom_id AS distribution_uom,
            distribution.vendor_id AS default_vendor,
            CASE WHEN sm.state in ('draft') THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS draft_qty,
            CASE WHEN sm.state in ('assigned') THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS available_qty,
            CASE WHEN sm.state in ('confirmed') THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS waiting_availability,
            CASE WHEN sm.state in ('transit') THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS transit_qty,
            CASE WHEN sm.state in ('processed') THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS processed_qty,
            CASE WHEN sm.state in ('waiting') THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS waiting_another_move,
            CASE WHEN sm.state in ('assigned', 'processed', 'transit') THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS reserve_qty,
            sm.picking_id AS picking_id,
            sp.state AS picking_state,
            CASE WHEN sm.state in ('assigned') AND sq.reservation_id IS NULL THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS not_reserved_available_qty,
            CASE WHEN sm.state in ('processed') AND sq.reservation_id IS NULL THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS not_reserved_processed_qty,
            CASE WHEN sm.state in ('transit') AND sq.reservation_id IS NULL THEN
                CASE WHEN distribution IS NOT NULL THEN
                    COALESCE((sm.product_uom_qty / pu.factor) * distribution.factor, 0.0)
                    ELSE COALESCE((sm.product_uom_qty / pu.factor), 0.0)
                    END
                ELSE 0.0
            END AS not_reserved_transit_qty
        FROM stock_move sm
        LEFT JOIN stock_quant sq ON sq.reservation_id = sm.id
        JOIN stock_picking sp ON sm.picking_id = sp.id
        JOIN stock_picking_type spt ON sp.picking_type_id = spt.id
        JOIN product_product pp ON sm.product_id = pp.id
        JOIN product_template pt ON pp.product_tmpl_id = pt.id
        JOIN product_uom pu ON sm.product_uom = pu.id
        LEFT JOIN product_supplierinfo ps ON ps.id = pu.vendor_id
        LEFT JOIN distribution_uom distribution ON distribution.product_id = pt.id
        WHERE {sql_location_string} AND {sql_product_string} AND {sql_state_string}
        AND {sql_company_string} AND {sql_picking_code_string} AND {sql_flush_date}
        """.format(**args) % self.get_distribution_uom(args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    def get_flush_date(self):
        """
        Get the latest flush date.
        """
        latest_flush_date = self.env['stock.flush.date'].search(
            [], order='flush_date desc', limit=1)
        if latest_flush_date:
            return latest_flush_date.flush_date
        return False

    def get_stock_quant_data(self, args):
        sql = """
            WITH distribution_uom AS (
                %s
            )
            SELECT
                sq.product_id AS product_id,
                pt.uom_id     AS standard_uom,
                distribution.uom_id AS distribution_uom,
                distribution.vendor_id AS default_vendor
            FROM stock_quant sq
            JOIN product_product pp ON sq.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            JOIN product_uom pu ON pt.uom_id = pu.id
            LEFT JOIN distribution_uom distribution ON distribution.product_id = pt.id
            WHERE {sq_location_string} AND {sq_product_string} AND {sq_company_string}
        """.format(**args) % self.get_distribution_uom(args)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    @api.multi
    def show_product(self):
        self.ensure_one()
        StockProductQty = self.env['stock.product.qty']
        ProductUom = self.env['product.uom']
        Product = self.env['product.product']

        stockproducts = self.env['stock.product.qty']

        state_list = ['draft', 'assigned', 'confirmed', 'transit', 'waiting', 'processed']

        picking_code_list = ['outgoing', 'internal']

        product_ids = self.product_ids.ids
        category_ids = self.product_category_ids
        if category_ids and not product_ids:
            products = Product.search([('categ_id', 'child_of', category_ids.ids)])
            product_ids = products.ids

        sql_product_string = '1=1'
        if self.product_category_ids and not product_ids:
            sql_product_string = '1=0'
        if product_ids:
            sql_product_string = 'pp.id in ' + str(product_ids).replace('[', '(').replace(']', ')')

        if self.warehouse_ids:
            warehouse_ids = self.warehouse_ids
        else:
            warehouse_ids = self.env['stock.warehouse'].search([('is_main_warehouse', '=', True)])
        location_ids = []
        if warehouse_ids:
            view_locations = [x.view_location_id.id for x in warehouse_ids]
            locations = self.env['stock.location'].search([('id', 'child_of', view_locations), ('is_stock_location', '=', True)])
            if locations:
                location_ids = locations.ids
        else:
            raise UserError('No main warehouse is being selected.\n '
                            'Kindly navigate to Inventory/Configuration/Warehouse Management and tick the checkbox '
                            '\'Is Main Warehouse\' for the main warehouses.')

        sql_flush_date = '1=1'
        flush_date = self.get_flush_date()
        if flush_date:
            sql_flush_date = "(pt.is_asset OR sm.date >= '%s')" % flush_date

        sql_location_string = '1=1'
        sq_location_string = '1=1'
        if location_ids:
            sql_location_string = 'sm.location_id in ' + str(location_ids).replace('[', '(').replace(']', ')')
            sq_location_string = 'sq.location_id in ' + str(location_ids).replace('[', '(').replace(']', ')')

        sql_state_string = 'sm.state in ' + str(state_list).replace('[', '(').replace(']', ')')

        sql_picking_code_string = 'spt.code in ' + str(picking_code_list).replace('[', '(').replace(']', ')')

        sql_company_string = 'sm.company_id = ' + str(self.env.user.company_id.id)

        sq_company_string = 'sq.company_id = ' + str(self.env.user.company_id.id)

        credentials = {
            'sql_location_string': sql_location_string,
            'sql_product_string': sql_product_string,
            'sql_state_string': sql_state_string,
            'sql_company_string': sql_company_string,
            'sql_picking_code_string': sql_picking_code_string,
            'sq_location_string': sq_location_string,
            'company_id': str(self.env.user.company_id.id),
            'sq_company_string': sq_company_string,
            'sql_flush_date': sql_flush_date,
        }
        move_dict = {}

        result = self.get_stock_move_data(credentials)
        for l in result:
            if l['product_id'] not in move_dict:
                move_dict[l['product_id']] = {
                    'product_id': l['product_id'],
                    'distribution_uom_id': l['distribution_uom'],
                    'standard_uom_id': l['standard_uom'],
                    'vendor_id': l['default_vendor'],
                    'draft_qty': l['draft_qty'],
                    'available_qty': l['available_qty'],
                    'waiting_availability': l['waiting_availability'],
                    'transit_qty': l['transit_qty'],
                    'processed_qty': l['processed_qty'],
                    'waiting_another_move': l['waiting_another_move'],
                    'reserve_qty': l['reserve_qty'],
                    'not_reserved_available_qty': l['not_reserved_available_qty'],
                    'not_reserved_processed_qty': l['not_reserved_processed_qty'],
                    'not_reserved_transit_qty': l['not_reserved_transit_qty'],
                    'pickings': [l['picking_id']] if (l['picking_id'] and l['picking_state'] not in ('done', 'cancel')) else [],
                }
            else:
                move_dict[l['product_id']]['draft_qty'] += l['draft_qty']
                move_dict[l['product_id']]['available_qty'] += l['available_qty']
                move_dict[l['product_id']]['waiting_availability'] += l['waiting_availability']
                move_dict[l['product_id']]['transit_qty'] += l['transit_qty']
                move_dict[l['product_id']]['processed_qty'] += l['processed_qty']
                move_dict[l['product_id']]['reserve_qty'] += l['reserve_qty']
                move_dict[l['product_id']]['waiting_another_move'] += l['waiting_another_move']
                move_dict[l['product_id']]['not_reserved_available_qty'] += l['not_reserved_available_qty']
                move_dict[l['product_id']]['not_reserved_processed_qty'] += l['not_reserved_processed_qty']
                move_dict[l['product_id']]['not_reserved_transit_qty'] += l['not_reserved_transit_qty']
                if l['picking_id'] and l['picking_state'] not in ('done', 'cancel'):
                    move_dict[l['product_id']]['pickings'].append(l['picking_id'])

        sq_product_string = '1=1'
        if self.product_category_ids and not product_ids:
            sq_product_string = '1=0'
        if product_ids:
            sq_product_string = 'pp.id in ' + str(product_ids).replace('[', '(').replace(']', ')')

        credentials.update({
            'sq_product_string': sq_product_string,
        })
        all_quant = self.get_stock_quant_data(credentials)
        for l in all_quant:
            if l['product_id'] not in move_dict:
                move_dict[l['product_id']] = {
                    'product_id': l['product_id'],
                    'distribution_uom_id': l['distribution_uom'],
                    'standard_uom_id': l['standard_uom'],
                    'vendor_id': l['default_vendor'],
                    'draft_qty': 0,
                    'available_qty': 0,
                    'waiting_availability': 0,
                    'transit_qty': 0,
                    'processed_qty': 0,
                    'waiting_another_move': 0,
                    'reserve_qty': 0,
                    'not_reserved_available_qty': 0,
                    'not_reserved_processed_qty': 0,
                    'not_reserved_transit_qty': 0,
                    'pickings': []
                }
        for product_key, product_data in move_dict.items():
            sq_location_string = '1=1'
            if location_ids:
                sq_location_string = 'sq.location_id in ' + str(location_ids).replace('[', '(').replace(']', ')')

            sq_product_string = 'sq.product_id = ' + str(product_key)

            sq_picking_code_string = 'spt.code in ' + str(picking_code_list).replace('[', '(').replace(']', ')')

            sq_company_string = 'sq.company_id = ' + str(self.env.user.company_id.id)

            quant_credentials = {
                'sq_location_string': sq_location_string,
                'sq_product_string': sq_product_string,
                'sq_picking_code_string': sq_picking_code_string,
                'sq_company_string': sq_company_string,
            }
            product = Product.browse(product_key)
            distribution_uom = ProductUom.browse(product_data['distribution_uom_id'])
            quant_on_hand_query = """
                SELECT
                    sum(sq.qty)
                FROM stock_quant AS sq
                where {sq_product_string} AND {sq_location_string} AND {sq_company_string} 
            """.format(**quant_credentials)
            self.env.cr.execute(quant_on_hand_query)
            result = self.env.cr.fetchone()
            qty_on_hand_raw = result and result[0] or 0.0
            qty_on_hand = qty_on_hand_raw
            if distribution_uom:
                qty_on_hand = ProductUom._compute_qty_obj(product.uom_id, qty_on_hand_raw, distribution_uom)
            quant_partial_available_query = """
                WITH distribution_uom AS (
                    %s
                )
                SELECT
                    SUM(CASE WHEN distribution IS NOT NULL THEN
                        COALESCE(sq.qty * distribution.factor, 0.0)
                        ELSE COALESCE(sq.qty, 0.0)
                    END) AS qty
                FROM stock_quant sq
                JOIN stock_move sm ON sq.reservation_id = sm.id
                JOIN product_product pp ON pp.id = sq.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN distribution_uom distribution ON distribution.product_id = pt.id
                WHERE {sq_product_string} AND {sq_location_string} and sm.state = 'confirmed'
                """.format(**quant_credentials) % self.get_distribution_uom(credentials)
            self.env.cr.execute(quant_partial_available_query)
            result = self.env.cr.fetchone()
            quant_partial_available_qty = result and result[0] or 0.0
            quant_partial_transit_query = """
                WITH distribution_uom AS (
                    %s
                )
                SELECT
                    SUM(CASE WHEN distribution IS NOT NULL THEN
                        COALESCE(sq.qty * distribution.factor, 0.0)
                        ELSE COALESCE(sq.qty, 0.0)
                    END) AS qty
                FROM stock_quant sq
                JOIN stock_move sm ON sq.reservation_id = sm.id
                JOIN product_product pp ON pp.id = sq.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN distribution_uom distribution ON distribution.product_id = pt.id
                WHERE {sq_product_string} AND {sq_location_string} and sm.state = 'transit'
                """.format(**quant_credentials) % self.get_distribution_uom(credentials)
            self.env.cr.execute(quant_partial_transit_query)
            result = self.env.cr.fetchone()
            quant_partial_transit_qty = result and result[0] or 0.0
            quant_partial_processed_query = """
               WITH distribution_uom AS (
                   %s
               )
               SELECT
                   SUM(CASE WHEN distribution IS NOT NULL THEN
                       COALESCE(sq.qty * distribution.factor, 0.0)
                       ELSE COALESCE(sq.qty, 0.0)
                   END) AS qty
               FROM stock_quant sq
               JOIN stock_move sm ON sq.reservation_id = sm.id
               JOIN product_product pp ON pp.id = sq.product_id
               JOIN product_template pt ON pt.id = pp.product_tmpl_id
               LEFT JOIN distribution_uom distribution ON distribution.product_id = pt.id
               WHERE {sq_product_string} AND {sq_location_string} and sm.state = 'processed'
               """.format(**quant_credentials) % self.get_distribution_uom(credentials)
            self.env.cr.execute(quant_partial_processed_query)
            result = self.env.cr.fetchone()
            quant_partial_processed_qty = result and result[0] or 0.0
            quant_free_query = """
                WITH distribution_uom AS (
                    %s
                )
                SELECT
                    SUM(CASE WHEN distribution IS NOT NULL THEN
                        COALESCE(sq.qty * distribution.factor, 0.0)
                        ELSE COALESCE(sq.qty, 0.0)
                    END) AS qty
                FROM stock_quant sq
                JOIN product_product pp ON pp.id = sq.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN distribution_uom distribution ON distribution.product_id = pt.id
                where {sq_product_string} AND {sq_location_string} AND sq.reservation_id IS NULL
            """.format(**quant_credentials) % self.get_distribution_uom(credentials)
            self.env.cr.execute(quant_free_query)
            result = self.env.cr.fetchone()
            quant_free_qty = result and result[0] or 0.0
            uoms = ProductUom.search([
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('vendor_id.name', '=', product_data['vendor_id'])
            ])
            if not uoms:
                uoms += (ProductUom.browse(product_data['standard_uom_id']))
            waiting_availability_qty = (product_data['waiting_availability'] - quant_partial_available_qty) or 0.0
            shortage_qty = (product_data['transit_qty'] - quant_partial_transit_qty +
                            product_data['processed_qty'] - quant_partial_processed_qty -
                            product_data['not_reserved_processed_qty'] - product_data['not_reserved_transit_qty'] ) or 0.0
            non_reserved_qty = product_data['not_reserved_available_qty'] + product_data['not_reserved_processed_qty'] +\
                              product_data['not_reserved_transit_qty']
            require_qty = product_data['draft_qty'] + product_data['waiting_another_move'] + waiting_availability_qty + non_reserved_qty + shortage_qty
            stock_product = StockProductQty.create({
                'product_id': product_data['product_id'],
                'uom_id': product_data['distribution_uom_id'] or product_data['standard_uom_id'],
                'available_qty': product_data['available_qty'] - product_data['not_reserved_available_qty'],
                'draft_qty': product_data['draft_qty'],
                'waiting_availablity': waiting_availability_qty,
                'partial_available_qty': quant_partial_available_qty,
                'transit_qty': quant_partial_transit_qty,
                'waiting_another_move': product_data['waiting_another_move'],
                'processed_qty': quant_partial_processed_qty,
                'force_availability_qty': non_reserved_qty,
                'shortage_qty': shortage_qty,
                'total_reverse': product_data['available_qty'] - product_data['not_reserved_available_qty'] + quant_partial_processed_qty + quant_partial_transit_qty + quant_partial_available_qty,
                'no_action': (quant_free_qty - require_qty),
                'free_reserve': quant_free_qty,
                'qty_on_hand': qty_on_hand,
                'qty_needed': require_qty,
                'picking_ids': [(6, 0, product_data['pickings'])],
                'uom_ids': [(6, 0, uoms.ids)],
                'distribution_uom_id': product_data['distribution_uom_id'],

                'back_available_qty': product_data['available_qty'] - product_data['not_reserved_available_qty'],
                'back_processed_qty': quant_partial_processed_qty,
                'back_transit_qty': quant_partial_transit_qty,
                'back_total_reverse': product_data['available_qty'] - product_data['not_reserved_available_qty'] + quant_partial_processed_qty + quant_partial_transit_qty + quant_partial_available_qty,
                'back_draft_qty': product_data['draft_qty'],
                'back_waiting_another_move': product_data['waiting_another_move'],
                'back_waiting_availablity': waiting_availability_qty,
                'back_partial_available_qty': quant_partial_available_qty,
                'back_shortage_qty': shortage_qty,
                'back_force_availability_qty': non_reserved_qty,
                'back_qty_needed': require_qty,
                'back_no_action': (quant_free_qty - require_qty),
                'back_free_reserve': quant_free_qty,
                'back_qty_on_hand': qty_on_hand,
            })
            stockproducts |= stock_product

        return {
            'type': 'ir.actions.act_window',
            'name': 'Current Inventory Status',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'stock.product.qty',
            'domain': [('id', 'in', stockproducts.ids)]
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
