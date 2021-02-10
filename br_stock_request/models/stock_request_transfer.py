from openerp import fields, models, api, registry, _
from openerp.exceptions import ValidationError
import logging
from common import UOM_TYPE
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz


_logger = logging.getLogger(__name__)
TRANSFER_STATE = [
    ('draft', 'Draft'),
    ('ordered', 'Ordered'),
    ('partially_available', 'Partially Available'),  # this state should be removed and however it remains due to some record is in this state
    ('assigned', 'Available'),  # this state should be removed and however it remains due to some record is in this state
    ('cancelled', 'Cancelled'),
    ('processing', 'Processing'),
    ('partially_processed', 'Partially Processed'),
    ('processed', 'Processed'),
    ('transit', 'Transit'),
    ('partially_delivered', 'Partially Delivered'),
    ('dropped', 'Order Dropped'),
    ('done', 'Done'),
    ('partially_delivered_dispute_raise', 'Partially Delivered & Dispute Raised'),
    ('partially_delivered_dispute_reject', 'Partially Delivered & Dispute Rejected'),
    ('partially_delivered_dispute_accept', 'Partially Delivered & Dispute Accepted'),
    ('dispute_raised', 'Dispute Raised'),
    ('dispute_rejected', 'Dispute Rejected'),
    ('dispute_confirmed', 'Dispute Accepted'),
    ('dispute_dropped', 'Dispute Dropped'),
    ('partially_dispute_rejected', 'Dispute Rejected Partially'),
    ('partially_dispute_accepted', 'Dispute Accepted Partially')
]

PICKING_STATE_WEIGHT = [
    {'state': 'draft', 'weight': 1},
    {'state': 'done', 'weight': 3},
    {'state': 'cancel', 'weight': 2},
    {'state': 'dropped', 'weight': 2},
    {'state': 'assigned', 'weight': 4},
    {'state': 'confirmed', 'weight': 4},
    {'state': 'partially_available', 'weight': 4},
    {'state': 'processed', 'weight': 5},
    {'state': 'transit', 'weight': 6},
    {'state': 'dispute_raised', 'weight': 7},
    {'state': 'dispute_accepted', 'weight': 8},
    {'state': 'dispute_rejected', 'weight': 9}
]

def status_getter(status):
    if not status:
        return 'draft'
    states = list(set(status))  # remove duplicate states
    # store the state along with weight for sorting purpose
    statelist = [(s['state'], s['weight']) for s in PICKING_STATE_WEIGHT for state in states if state == s['state']]
    # sort the state based on the weight and only store top 2
    sortedstate = sorted(statelist, key=lambda s: s[1], reverse=True)[0:2]
    # store the top 2 states to determine the ordering status
    finalstate = [ss[0] for ss in sortedstate]
    if all([s == 'draft' for s in finalstate]):
        return 'ordered'
    elif all([s == 'dropped' for s in finalstate]):
        return 'dropped'
    elif all([s == 'done' for s in finalstate]):
        return 'done'
    elif all([s == 'cancel' for s in finalstate]):
        return 'cancelled'
    elif all([s in ('done', 'cancel', 'dropped') for s in finalstate]):
        return 'done'
    elif all([s in ('transit', 'cancel', 'dropped') for s in finalstate]):
        return 'transit'
    elif all([s in ('processed', 'transit', 'cancel', 'dropped') for s in finalstate]):
        return 'processed'
    elif all([s in ('draft', 'cancel', 'dropped') for s in finalstate]):
        return 'partially_processed'
    elif all([s in ('draft', 'assigned', 'confirmed', 'partially_available', 'cancel', 'dropped') for s in finalstate]):
        return 'processing'
    elif all([s == 'dispute_raised' for s in finalstate]) or (any([s == 'dispute_raised' for s in finalstate]) and any(
            [s in ('done', 'cancel', 'dropped') for s in finalstate])):
        return 'dispute_raised'
    elif all([s == 'dispute_rejected' for s in finalstate]) or (any([s == 'dispute_rejected' for s in finalstate]) and any(
            [s in ('done', 'cancel', 'dropped') for s in finalstate])):
        return 'dispute_dropped'
    elif all([s == 'dispute_accepted' for s in finalstate]) or (any([s == 'dispute_accepted' for s in finalstate]) and any(
            [s in ('done', 'cancel', 'dropped') for s in finalstate])):
        return 'dispute_confirmed'
    elif any([s == 'dispute_accepted' for s in finalstate]) and any([s in ('dispute_rejected', 'dispute_raised') for s in finalstate]):
        return 'partially_dispute_accepted'
    elif any([s == 'dispute_rejected' for s in finalstate]) and any([s == 'dispute_raised' for s in finalstate]):
        return 'partially_dispute_rejected'
    elif any([s == 'dispute_raised' for s in finalstate]) and any(
            [s in ('draft', 'assigned', 'confirmed', 'partially_available', 'processed', 'transit') for s in finalstate]):
        return 'partially_delivered_dispute_raise'
    elif any([s == 'dispute_rejected' for s in finalstate]) and any(
            [s in ('draft', 'assigned', 'confirmed', 'partially_available', 'processed', 'transit') for s in finalstate]):
        return 'partially_delivered_dispute_reject'
    elif any([s == 'dispute_accepted' for s in finalstate]) and any(
            [s in ('draft', 'assigned', 'confirmed', 'partially_available', 'processed', 'transit') for s in finalstate]):
        return 'partially_delivered_dispute_accept'
    elif any([s == 'done' for s in finalstate]) and any(
            [s in ('draft', 'assigned', 'confirmed', 'partially_available', 'processed', 'transit') for s in finalstate]):
        return 'partially_delivered'
    elif any([s in ('processed', 'transit') for s in finalstate]) and any(
            [s in ('draft', 'assigned', 'confirmed', 'partially_available') for s in finalstate]):
        return 'partially_processed'


class StockRequestTransferCronLog(models.Model):
    _name = 'br.stock.request.transfer.cron.log'
    _description = 'Log file that keep track of the scheduled action for confirm transfer request'

    name = fields.Date(string='Date')
    total_transfer = fields.Integer(string='Total Transfer Included')
    success_transfer = fields.Integer(string='Success Transfer')
    fail_transfer = fields.Integer(string='Failed Transfer')
    log_line_ids = fields.One2many('br.stock.request.transfer.cron.log.line', inverse_name='log_id', string="Log Lines")


class StockRequestTransferCronLogLine(models.Model):
    _name = 'br.stock.request.transfer.cron.log.line'
    _description = 'Log line of a transfer in the scheduled action for confirm transfer request'

    log_id = fields.Many2one(comodel_name='br.stock.request.transfer.cron.log', string='Request Transfer Log')
    picking_id = fields.Many2one(comodel_name='stock.picking', string="Picking")
    picking_state = fields.Char(string='Picking State')
    current_state = fields.Selection(related='picking_id.state')
    start_run_time = fields.Datetime(string='Start Running Time')


class StockRequestTransfer(models.Model):
    _name = 'br.stock.request.transfer'
    _order = 'id DESC'
    _inherit = 'mail.thread'

    name = fields.Char(string="Name", default="/", copy=False)
    warehouse_id = fields.Many2one(comodel_name='stock.warehouse', string="Deliver From")
    dest_warehouse_id = fields.Many2one(comodel_name='stock.warehouse', string="Deliver To")
    form_id = fields.Many2one(comodel_name='br.stock.request.form', string="Order Form", ondelete='restrict')
    form_warehouse_ids = fields.Many2many(comodel_name='stock.warehouse', string="Warehouses",
                                          related='form_id.warehouse_ids')
    date_order = fields.Datetime(string="Order Date", copy=False)
    expected_date = fields.Datetime(string="Delivery Date")
    requestor_id = fields.Many2one(comodel_name='res.users', string="Requestor", copy=False)
    schedule_date = fields.Datetime(string="Schedule Date", copy=False, compute='_get_transfer_info', store=True)
    received_date = fields.Datetime(string="Received Date", copy=False)
    operator_id = fields.Many2one(string="Logistics Operator", comodel_name='res.users', copy=False, compute='_get_transfer_info')
    driver = fields.Many2one(string="Driver", comodel_name='res.partner', copy=False, store=True, compute='_get_transfer_info', ondelete='restrict')
    truck = fields.Many2one(string="Truck", comodel_name='br.fleet.vehicle',copy=False, store=True, compute='_get_transfer_info', ondelete='restrict')
    packer = fields.Many2one(string="Picker/Packer", comodel_name='res.partner', copy=False, store=True, compute='_get_transfer_info')
    line_ids = fields.One2many(string="Lines", comodel_name='br.stock.request.transfer.line',
                               inverse_name='transfer_id', copy=True)
    picking_ids = fields.One2many(string="Pickings", comodel_name='stock.picking', inverse_name='request_id')
    picking_count = fields.Integer(compute='_compute_picking', string='Receptions', default=0)
    outlet_id = fields.Many2one(string="Outlet", comodel_name='br_multi_outlet.outlet', compute="_get_outlet_id", store=True)
    state = fields.Selection(selection=TRANSFER_STATE, string="Status", default='draft', compute='_get_state',
                             help="""
                            * draft: when there is no picking\n
                            * ordered: all picking in draft\n
                            * dropped: logistic cancels before transit\n
                            * cancelled: outlet cancels before transit\n
                            * processing: if all picking state in available, waiting availability, and partially available\n
                            * partially_processed: if one of the picking state in processed and another one in draft or processing\n
                            * processed: if all picking state in processed\n
                            * transit: if one of the picking state in transit and another one in cancel or transit\n
                            * partially_delivered: at least one done and another in other state\n
                            * partially_delivered_dispute_raise: at least one done and another one in dispute_raised\n 
                            * partially_delivered_dispute_reject: at least one done and another one in dispute_rejected\n 
                            * partially_delivered_dispute_accept: at least one done and another one in dispute_accepted\n 
                            * dispute_raised: outlet raise dispute\n
                            * dispute_rejected: reverse transfer is cancel\n
                            * dispute_accepted: reverse transfer is done\n
                            * partially_dispute_rejected: if two pickings raise dispute, one is rejected and another one in draft\n
                            * partially_dispute_accepted: if two pickings raise dispute, one is accepted and another one in draft or cancel\n
                            * done: all done without reverse (exclude cancels)\n
                            """,
                             store=True)
    dispute_time = fields.Datetime(string="Dispute Time", copy=False)
    closed_time = fields.Datetime(string="Closed Time", copy=False)
    remark = fields.Text(String="Remark")
    form_source_warehouse = fields.Many2many('stock.warehouse', 'br_stock_req_transf_stock_from_source_warehouse_rel', 'transfer_request_id', 'warehouse_id', store=True, compute='get_warehouse_domain')

    @api.multi
    @api.depends('form_id')
    def get_warehouse_domain(self):
        for r in self:
            if r.form_id.warehouse_ids:
                warehouses = r.form_id.warehouse_ids
                source_warehouses = [x.id for x in warehouses]
            else:
                warehouses = self.env['stock.warehouse'].search([])
                source_warehouses = [x.id for x in warehouses]
            r.form_source_warehouse = [(6, 0, source_warehouses)]

    @api.depends('picking_ids', 'picking_ids.driver', 'picking_ids.vehicle')
    @api.multi
    def _get_transfer_info(self):
        """Get most recent transfer information (exclude dispute transfer)"""
        for t in self:
            picking = t.picking_ids.filtered(lambda x: not x.picking_orig_id).sorted(key=lambda r: r.min_date, reverse=True)
            if picking:
                t.driver = picking[0].driver.id if picking[0].driver else False
                t.truck = picking[0].vehicle.id if picking[0].vehicle else False
                t.packer = picking[0].packer.id if picking[0].packer else False
                t.schedule_date = picking[0].min_date
                t.operator_id = picking[0].write_uid.id

    @api.depends('dest_warehouse_id')
    @api.multi
    def _get_outlet_id(self):
        for t in self:
            outlet = t.dest_warehouse_id.get_outlet()
            t.outlet_id = outlet.id

    @api.multi
    @api.depends('picking_ids.state')
    def _get_state(self):
        """
        * draft: when there is no picking\n
        * ordered: all picking in draft\n
        * dropped: logistic cancels before transit\n
        * cancelled: outlet cancels before transit\n
        * processing: if all picking state in available, waiting availability, and partially available\n
        * partially_processed: if one of the picking state in processed and another one in draft or processing\n
        * processed: if all picking state in processed\n
        * transit: if one of the picking state in transit and another one in cancel or transit\n
        * partially_delivered: at least one done and another in other state\n
        * partially_delivered_dispute_raise: at least one done and another one in dispute_raised\n
        * partially_delivered_dispute_reject: at least one done and another one in dispute_rejected\n
        * partially_delivered_dispute_accept: at least one done and another one in dispute_accepted\n
        * dispute_raised: outlet raise dispute\n
        * dispute_rejected: reverse transfer is cancel\n
        * dispute_accepted: reverse transfer is done\n
        * partially_dispute_rejected: if two pickings raise dispute, one is rejected and another one in draft\n
        * partially_dispute_accepted: if two pickings raise dispute, one is accepted and another one in draft or cancel\n
        * done: all done without reverse (exclude cancels)\n
        """
        # TODO: i know some iterations aren't needed, but get the job done first ...
        for transfer in self:
            # store the state of every picking
            status = []
            # store the picking which has raised dispute
            picking_has_dispute = [x.picking_orig_id.id for x in transfer.picking_ids if x.picking_orig_id and x.picking_type_id.is_dispute is True]
            for pick in transfer.picking_ids:
                if pick.id in picking_has_dispute:
                    continue  # if the picking has raised a dispute, it will be skipped
                state = pick.state
                # if the picking is a dispute picking, the state name will be changed based on the real state.
                if pick.picking_orig_id and pick.picking_type_id.is_dispute is True:
                    state = 'dispute_accepted' if pick.state == 'done' else 'dispute_rejected' if pick.state == 'cancel' else 'dispute_raised'
                # if is_logistic_cancel is true and the state is 'cancel', then the state should be 'dropped'.
                if (pick.is_logistic_cancel and pick.state == 'cancel') or pick.state == 'undelivered':
                    state = 'dropped'
                status.append(state)
            transfer.state = status_getter(status)

    @api.onchange('form_id')
    def onchange_form_id(self):
        lines = [(5, False, False)]
        if self.form_id:
            for l in self.form_id.line_ids_related:
                # Get uom from vendors
                uom_id = False
                sellers = l.product_id.seller_ids
                if l.uom_type == 'standard':
                    uom_id = l.product_id.uom_id.id
                else:
                    uom_type_map = {
                        'purchase': 'is_po_default',
                        'storage': 'is_storage',
                        'distribution': 'is_distribution',
                    }
                    for s in sellers:
                        for u in s.uom_ids:
                            # Select first uom which has same uom type in transfer line
                            if getattr(u, uom_type_map[l.uom_type]):
                                uom_id = u.id
                                break
                    if not uom_id:
                        uom_id = l.product_id.uom_id.id
                val = {
                    'product_id': l.product_id.id,
                    'uom_id': uom_id,
                    'uom_type': l.uom_type
                }
                lines.append((0, 0, val))
        self.line_ids = lines
        self.recompute_qty_on_hand()
        if self.form_id and len(self.form_id.warehouse_ids) == 1:
            self.warehouse_id = self.form_id.warehouse_ids.id

    @api.model
    def create(self, vals):
        if ('name' not in vals) or (vals.get('name') in ('/', False)):
            # Set name for transfer request by sequence in warehouse, if can't find one then get default sequence
            warehouse_id = vals.get('dest_warehouse_id', False)
            sequence = self.env['stock.warehouse'].browse(warehouse_id).sequence_id
            if not sequence:
                sequence = self.env.ref('br_stock_request.br_request_transfer_general_sequence', False)
            vals['name'] = sequence.next_by_id()
        return super(StockRequestTransfer, self).create(vals)

    @api.multi
    def action_view_picking(self):
        '''
        This function returns an action that display existing picking orders of given purchase order ids.
        When only one found, show the picking immediately.
        '''
        action = self.env.ref('stock.action_picking_tree')
        result = action.read()[0]

        # override the context to get rid of the default filtering on picking type
        result['context'] = {}
        pick_ids = sum([order.picking_ids.ids for order in self], [])
        # choose the view_mode accordingly
        if len(pick_ids) > 1:
            result['domain'] = "[('id','in',[" + ','.join(map(str, pick_ids)) + "])]"
        elif len(pick_ids) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = pick_ids and pick_ids[0] or False
        return result

    @api.depends('picking_ids')
    def _compute_picking(self):
        """Get number picking that associate with transfer request"""
        for s in self:
            s.picking_count = len(s.picking_ids)

    def _prepare_picking_val(self):
        """Prepare picking values"""
        return {
            'location_id': self.warehouse_id.lot_stock_id.id,
            'location_dest_id': self.dest_warehouse_id.lot_stock_id.id,
            'origin': self.name,
            'driver': self.driver.id if self.driver else False,
            'truck': self.truck.id,
            'packer': self.packer.id if self.packer else False,
            'picking_type_id': self.warehouse_id.out_type_id.id,
            'min_date': self.expected_date,
            'move_lines': self._prepare_move_val(),
            'request_id': self.id,
        }

    def _prepare_move_val(self):
        """Generate stock move from transfer line"""
        vals = []
        analytic_account = self.dest_warehouse_id.lot_stock_id.get_analytic_account()
        for l in self.line_ids:
            vals.append((0, 0, {
                'request_line_id': l.id,
                'name': l.product_id.name_template,
                'product_id': l.product_id.id,
                'product_uom_qty': l.ordered_qty,
                'product_uom': l.uom_id.id,
                'account_analytic_id': analytic_account if analytic_account else False,
                'state': 'draft',
                'request_id': l.transfer_id.id
            }))
        return vals

    @api.multi
    def action_request(self):
        self.ensure_one()
        # Remove all lines that have order qty <= 0
        to_unlink_lines = self.env['br.stock.request.transfer.line']
        for l in self.line_ids:
            if l.ordered_qty <= 0:
                to_unlink_lines |= l
        if to_unlink_lines:
            to_unlink_lines.unlink()
        if not self.line_ids or len(self.line_ids) <= 0:
            raise ValidationError(
                _("You can not send order because ordered quantity for all products are 0 now. Please update it before you send order !"))
        # Create transfer
        self.env['stock.picking'].create(self._prepare_picking_val())
        self.write({'state': 'ordered', 'requestor_id': self.env.user.id, 'date_order': datetime.now()})

    @api.model
    def confirm_transfer_request(self):
        def get_last_sec(from_timezone, to_timezone, date):
            from_tz = date.replace(tzinfo=pytz.timezone(from_timezone))
            to_tz = from_tz.astimezone(pytz.timezone(to_timezone))
            last_sec_to_tz = to_tz.replace(hour=23, minute=59, second=59)
            final_to_tz = last_sec_to_tz.astimezone(pytz.timezone(from_timezone))
            return final_to_tz.strftime("%Y-%m-%d %H:%M:%S")
        utc_last_sec = get_last_sec('UTC', self.env.user.tz, datetime.now())
        todos = self.env['stock.picking'].search([('state', '=', 'transit'), ('min_date', '<=', utc_last_sec)])
        log_obj = self.env['br.stock.request.transfer.cron.log']
        log_lines_obj = self.env['br.stock.request.transfer.cron.log.line']
        log_lines = []
        log = log_obj.create({
            'name': datetime.now().date(),
        })
        for picking in todos:
            cronjob_user = picking.company_id.cronjob_user
            vals = {
                'log_id': log.id,
                'picking_id': picking.id,
                'start_run_time': datetime.now(),
            }
            log_line = log_lines_obj.create(vals)
            if cronjob_user:
                self.sudo(cronjob_user).confirm_picking(picking, log_line)
            else:
                self.confirm_picking(picking, log_line)
            log_lines.append(log_line)
        log.write({
            'log_line_ids': [(6, 0, [line.id for line in log_lines])],
            'total_transfer': len(log_lines),
            'success_transfer': len([line.id for line in log_lines if line['picking_state'] == 'Success']),
            'fail_transfer': len([line.id for line in log_lines if line['picking_state'] != 'Success'])
        })

    def confirm_picking(self, picking, log_line):
        with api.Environment.manage():
            with registry(self.env.cr.dbname).cursor() as new_cr:
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                picking = picking.with_env(new_env)
                try:
                    picking.do_process_transfer_done()
                    picking.write({'auto_transit_log': 'success!'})
                    log_line.write({'picking_state': 'Success'})
                except Exception as e:
                    new_env.cr.rollback()
                    picking.write({'auto_transit_failed': True, 'auto_transit_log': str(e)})
                    _logger.info(str(e))
                    log_line.write({'picking_state': str(e)})
                new_env.cr.commit()

    @api.multi
    def action_cancel_confirm(self):
        self.ensure_one()
        view = self.env.ref('br_stock_request.view_transfer_cancel_confirmation_form').id
        return {
            'name': _('Transfer Cancel'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'transfer.cancel.confirmation',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'context': {'active_id': self.id, 'active_ids': self.ids},
        }

    @api.multi
    def action_cancel(self):
        for transfer in self:
            for picking in transfer.picking_ids:
                picking.action_cancel()

    @api.multi
    def recompute_qty_on_hand(self):
        uom_obj = self.env['product.uom']
        product_ids = self.env['product.product']
        for transfer in self:
            # for line in transfer.line_ids:
            #     line.qty_on_hand = line._get_qty_on_hand()

            # NOTE : comment above two line, and added bellow code to improve the speed.
            for line in transfer.line_ids.filtered(lambda x: x.product_id):
                product_ids += line.product_id
            location_id = transfer.dest_warehouse_id.lot_stock_id.id
            product_qties = product_ids.with_context(location=location_id)._product_available()
            for line in transfer.line_ids:
                if line.product_id and line.uom_id:
                    qty_on_hand = product_qties[line.product_id.id]['qty_available']
                    qty_on_hand = uom_obj._compute_qty_obj(line.product_id.uom_id, qty_on_hand, line.uom_id)
                    line.qty_on_hand = qty_on_hand

    @api.onchange('dest_warehouse_id')
    def onchange_dest_warehouse_id(self):
        if self.dest_warehouse_id:
            current_date = datetime.strftime(datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
            domain = [('warehouse_dest_ids', '=', self.dest_warehouse_id.id),
            '|','|','|',
            '&', ('from_date', '<=', current_date),
            ('to_date', '>=', current_date),
            '&', ('from_date', '<=', current_date),
            ('to_date', '=', None),
            '&', ('from_date', '=', None),
            ('to_date', '>=', current_date),
            '&', ('from_date', '=', None),
            ('to_date', '=', None)]
            order_form_ids = self.env['br.stock.request.form'].search(domain)
            if len(order_form_ids) == 1:
                self.form_id = order_form_ids.id


class StockRequestTransferLine(models.Model):
    _name = 'br.stock.request.transfer.line'

    @api.model
    def _get_qty_on_hand(self):
        qty_on_hand = 0
        if self.product_id and self.uom_id:
            product = self.product_id
            location_id = self.transfer_id.dest_warehouse_id.lot_stock_id.id
            product_qties = product.with_context(location=location_id)._product_available()
            qty_on_hand = product_qties[product.id]['qty_available']
            qty_on_hand = self.env['product.uom']._compute_qty_obj(self.product_id.uom_id, qty_on_hand, self.uom_id)
        return qty_on_hand

    transfer_id = fields.Many2one(comodel_name='br.stock.request.transfer', string="Request Transfer")
    product_id = fields.Many2one(comodel_name='product.product', string="Product")
    uom_id = fields.Many2one(comodel_name='product.uom', string="Unit of Measure")
    qty_on_hand = fields.Float(string="Qty On Hand", default=_get_qty_on_hand, digits=(18, 2))
    # TODO: remember why need to create related field ...
    qty_on_hand_related = fields.Float(related="qty_on_hand", string="Qty On Hand", digits=(18, 2), readonly=1)
    ordered_qty = fields.Float(string="Ordered Qty", default=0, digits=(18, 2))
    committed_qty = fields.Float(string="Committed Qty", default=0, digits=(18, 2), copy=False)
    delivered_qty = fields.Float(string="Delivered Qty", default=0, digits=(18, 2), store=True,
                                 copy=False)
    dispute_qty = fields.Float(string="Dispute Qty", default=0, digits=(18, 2), store=True, copy=False)
    pending_qty = fields.Float(string="Unfulfilled Qty", default=0, digits=(18, 2), compute='_get_pending_qty', store=True,
                               copy=False)
    move_ids = fields.One2many(comodel_name='stock.move', inverse_name='request_line_id')
    uom_type = fields.Selection(selection=UOM_TYPE, string="UOM Type")
    # Transfer informations
    state = fields.Selection(related='transfer_id.state', default='draft')
    dest_warehouse_id = fields.Many2one(related='transfer_id.dest_warehouse_id', comodel_name='stock.warehouse',
                                        string="Deliver To", store=True)
    warehouse_id = fields.Many2one(related='transfer_id.warehouse_id', comodel_name='stock.warehouse',
                                   string="Deliver From", store=True)
    date_order = fields.Datetime(related='transfer_id.date_order', string="Order Date")
    expected_date = fields.Datetime(related='transfer_id.expected_date', string="Delivery Date")
    schedule_date = fields.Datetime(related='transfer_id.schedule_date', string="Schedule Date", store=True)

    schedule_expected_diff = fields.Integer(string="Schedule & Expected Time Diff", compute='_get_schedule_expected_diff', store=True)

    @api.depends('schedule_date', 'expected_date')
    @api.multi
    def _get_schedule_expected_diff(self):
        """

        :return: (Float) Time difference in days
        """
        for sp in self:
            if not sp.expected_date and not sp.schedule_date:
                diff = 0
            elif not sp.expected_date:
                diff = -1
            elif not sp.schedule_date:
                diff = 1
            else:
                expected_date, schedule_date = sp.expected_date, sp.schedule_date
                if isinstance(sp.expected_date, str):
                    expected_date = datetime.strptime(sp.expected_date, DEFAULT_SERVER_DATETIME_FORMAT)
                if isinstance(sp.schedule_date, str):
                    schedule_date = datetime.strptime(sp.schedule_date, DEFAULT_SERVER_DATETIME_FORMAT)
                diff = (expected_date.date() - schedule_date.date()).total_seconds() / 86400
            sp.schedule_expected_diff = diff

    @api.onchange('product_id', 'uom_id')
    def onchange_product_id(self):
        self.qty_on_hand = self._get_qty_on_hand()

    @api.depends('transfer_id', 'ordered_qty', 'committed_qty')
    def _get_pending_qty(self):
        for line in self:
            line.pending_qty = line.ordered_qty - line.committed_qty

    @api.constrains('ordered_qty', 'committed_qty', 'delivered_qty')
    def _check_qty(self):
        for line in self:
            if line.ordered_qty < 0:
                raise ValidationError(
                    _("Ordered Qty, Commited Qty and Delivered Qty must be greater or equal to zero !"))