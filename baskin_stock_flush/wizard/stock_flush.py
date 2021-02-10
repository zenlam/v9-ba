# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError
from datetime import datetime


class StockFlushLocationCreation(models.TransientModel):
    """
    This wizard will create a flush location for warehouse.
    """

    _name = "stock.flush.location.creation"
    _description = "Create flush location for warehouses"

    flush_location_name = fields.Char(string='Flush Location Name',
                                      required=True,
                                      help='This field will be used in naming '
                                           'the flush locations.',)

    @api.multi
    def create_flush_location(self):
        # get the selected warehouses id from context
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['stock.warehouse'].browse(active_ids):
            # create flush location
            flush_location_vals = record._prepare_flush_location()
            flush_location_vals['name'] = self.flush_location_name
            flush_location = \
                self.env['stock.location'].create(flush_location_vals)
            record.wh_flush_stock_loc_id = flush_location
        return {'type': 'ir.actions.act_window_close'}


class StockFlushOperation(models.TransientModel):
    """
    This wizard will move the quants from stock location to flush location for
    a warehouse.
    """
    _name = "stock.flush.operation"
    _description = "Flush the stock quants of the warehouse to flush location"

    warehouse_ids = fields.Many2many(comodel_name='stock.warehouse',
                                     string="Warehouse",
                                     required=True)
    flush_date = fields.Datetime(string='Flush Date', required=True)
    select_all = fields.Boolean(string='Select All Warehouses')

    @api.onchange('select_all')
    def onchange_select_all(self):
        if self.select_all:
            all_warehouses = self.env['stock.warehouse'].search([])
            self.warehouse_ids = all_warehouses.ids
        else:
            self.warehouse_ids = False

    @api.multi
    def action_check_picking_validity(self):
        """
        Perform picking validity checking.
        """
        picking_list = self.check_picking_validity()
        # perform session validity checking
        session_list = self.check_session_validity()
        # perform validated picking checking
        validated_picking_list = self.check_picking_validated()
        if picking_list:
            pickings_str = '\n'.join(picking_list)
            raise ValidationError(_("Please settle these pickings before "
                                    "flushing: \n%s") % pickings_str)
        if session_list:
            empty_session = []
            for session in session_list:
                orders = self.env['pos.order'].search([
                    ('session_id', '=', session.id)
                ])
                if orders:
                    for order in orders:
                        if any(line.product_id.product_tmpl_id.type
                               != 'service' for line in order.lines):
                            empty_session.append(session)
                            break
            if empty_session:
                session_str = '\n'.join([s.name for s in empty_session])
                raise ValidationError(_(
                    "Session does not have any picking:\n%s"
                ) % session_str)
        if validated_picking_list:
            picking_str = '\n'.join(validated_picking_list)
            raise ValidationError(_(
                "Please make sure all POS-related picking is validated before "
                "the flush operation: \n%s"
            ) % picking_str)
        raise ValidationError(_("No invalid picking or session is found."))

    @api.multi
    def check_picking_validated(self):
        """
        Check the picking is validated for closed & validated sessions
        """
        for res in self:
            # get all warehouse ids
            wh_ids = ','.join([str(q.id) for q in res.warehouse_ids])
            # Check all the picking that generated from pos session is validated
            picking_query = """
                SELECT distinct(sp.name)
                FROM stock_picking sp
                JOIN pos_session ps ON sp.id = ps.picking_id
                JOIN br_multi_outlet_outlet mo ON mo.id = ps.outlet_id
                JOIN stock_warehouse sw ON sw.id = mo.warehouse_id
                WHERE ps.picking_id IS NOT NULL
                AND ps.state = 'closed'
                AND sp.state != 'done'
                AND sw.id IN (%s)

                UNION

                SELECT distinct(sp.name)
                FROM stock_picking sp
                JOIN pos_order po ON sp.id = po.picking_id
                JOIN br_multi_outlet_outlet mo ON mo.id = po.outlet_id
                JOIN stock_warehouse sw ON sw.id = mo.warehouse_id
                WHERE po.picking_id IS NOT NULL
                AND po.state = 'done'
                AND sp.state != 'done'
                AND sw.id IN (%s)
            """ % (wh_ids, wh_ids)
            self.env.cr.execute(picking_query)
            validated_picking_list = self.env.cr.fetchall()
            return validated_picking_list

    @api.multi
    def check_session_validity(self):
        """
        Check all close & validated sessions have picking
        """
        for res in self:
            # get all warehouse ids
            session_ids = False
            wh_ids = ','.join([str(q.id) for q in res.warehouse_ids])
            session_query = """
                    SELECT DISTINCT ps.id FROM pos_session ps
                    JOIN pos_order po ON ps.id = po.session_id
                    JOIN br_multi_outlet_outlet mo ON mo.id = po.outlet_id
                    JOIN stock_warehouse sw ON sw.id = mo.warehouse_id
                    WHERE po.picking_id IS NULL
                    AND ps.picking_id IS NULL
                    AND sw.id IN (%s)
                    """ % wh_ids
            self.env.cr.execute(session_query)
            sessions = self.env.cr.fetchall()
            if sessions:
                session_list = [session[0] for session in sessions]
                session_ids = self.env['pos.session'].browse(session_list)
            return session_ids

    @api.multi
    def check_picking_validity(self):
        """
        Check all pickings which deliver Stockable/Consumable (non-assets) from
        warehouse stock location and state is not Done/Cancel. Excluding the
        incoming shipment.
        """
        for res in self:
            stock_locations = [warehouse.lot_stock_id.id
                               for warehouse in res.warehouse_ids]
            # Check all the stock move that has source location from warehouse
            # stock location
            self.env.cr.execute("""
                SELECT
                    distinct(sp.name)
                FROM stock_move sm
                JOIN stock_picking sp ON sm.picking_id = sp.id
                JOIN stock_picking_type spt ON sp.picking_type_id = spt.id
                JOIN product_product pp ON sm.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE (sm.location_id in %s OR sm.location_dest_id in %s)
                AND sp.state not in ('done', 'cancel')
                AND pt.is_asset = false
                AND spt.code != 'incoming'
            """, (tuple(stock_locations), tuple(stock_locations),))
            pickings = self.env.cr.fetchall()
            picking_list = [p for pick in pickings for p in pick]
            return picking_list

    @api.multi
    def check_all_warehouses(self):
        """
        Flush operation can only be executed when the user selects all
        warehouses
        """
        for res in self:
            all_warehouses = self.env['stock.warehouse'].search([])
            if len(all_warehouses) != len(res.warehouse_ids):
                raise UserError(_("Select all warehouses in order to "
                                  "perform flush."))

    @api.multi
    def action_flush(self):
        self.check_all_warehouses()
        picking_list = self.check_picking_validity()
        if picking_list:
            pickings_str = '\n'.join(picking_list)
            raise ValidationError(_("Please settle these pickings before "
                                    "flushing: \n%s") % pickings_str)
        session_list = self.check_session_validity()
        if session_list:
            empty_session = []
            for session in session_list:
                orders = self.env['pos.order'].search([
                    ('session_id', '=', session.id)
                ])
                if orders:
                    for order in orders:
                        if any(line.product_id.product_tmpl_id.type
                               != 'service' for line in order.lines):
                            empty_session.append(session)
                            break
            if empty_session:
                session_str = '\n'.join([s.name for s in empty_session])
                raise ValidationError(_(
                    "Session does not have any picking:\n%s"
                ) % session_str)
        flush_date_obj = self.env['stock.flush.date']
        flush_report_obj = self.env['stock.flush.report']
        validated_picking_list = self.check_picking_validated()
        if validated_picking_list:
            picking_str = '\n'.join(validated_picking_list)
            raise ValidationError(_(
                "Please make sure all POS-related picking is validated before "
                "the flush operation: \n%s"
            ) % picking_str)
        for res in self:
            # raise error for no flush location of warehouse
            warehouse_without_flush = [warehouse.name
                                       for warehouse in res.warehouse_ids
                                       if not warehouse.wh_flush_stock_loc_id]
            if warehouse_without_flush:
                raise UserError(('Warehouses does not have a flush location:\n'
                                '%s') % '\n'.join(warehouse_without_flush))

            flush_date = datetime.strptime(
                res.flush_date, "%Y-%m-%d %H:%M:%S").date()

            for warehouse in res.warehouse_ids:
                stock_location = warehouse.lot_stock_id
                flush_location = warehouse.wh_flush_stock_loc_id
                # get the quants ids which is from warehouse stock location and
                # the product type is Stockable and Consumable
                # (excluding asset).
                quants_query = """
                SELECT
                    sq.id
                FROM stock_quant sq
                JOIN product_product pp ON sq.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                JOIN stock_location sl ON sq.location_id = sl.id
                WHERE sl.id = %s
                AND pt.type in ('product', 'consu')
                AND pt.is_asset = false
                """ % stock_location.id
                self.env.cr.execute(quants_query)
                quants = self.env.cr.fetchall()
                quant_ids = [q[0] for q in quants]

                # if the stock location has quants, then flush the quants to
                # flush location.
                if quants:
                    flush_query = """
                    UPDATE stock_quant sq1 
                    SET location_id = %s
                    FROM stock_quant sq2
                    JOIN product_product pp ON sq2.product_id = pp.id
                    JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    JOIN stock_location sl ON sq2.location_id = sl.id
                    WHERE sq1.id = sq2.id
                    AND sl.id = %s
                    AND pt.type in ('product', 'consu')
                    AND pt.is_asset = false
                    """ % (flush_location.id, stock_location.id)
                    self.env.cr.execute(flush_query)

                # prepare the values for stock flush report creation
                flush_name = "%s-%s" % (warehouse.name,
                                        flush_date.strftime("%Y%m%d"))
                flush = flush_report_obj.create({
                    'name': flush_name,
                    'warehouse_id': warehouse.id,
                    'location_id': flush_location.id,
                    'flush_date': res.flush_date,
                })

                # link the stock quants with the flush report
                if quants:
                    update_quants_query = """
                    UPDATE stock_quant
                    SET flush_id = %s
                    WHERE id in (%s)
                    """ % (flush.id, ','.join([str(q) for q in quant_ids]))
                    self.env.cr.execute(update_quants_query)
            flush_date_obj.create({
                'name':  flush_date.strftime("%Y%m%d"),
                'flush_date': res.flush_date,
            })
        return {'type': 'ir.actions.act_window_close'}
