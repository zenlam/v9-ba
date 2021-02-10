from openerp import models, api, fields, _
from openerp.addons.stock.stock import stock_picking
from openerp.osv import osv, fields as Fields
from openerp.exceptions import UserError, ValidationError
from lxml import etree
from openerp.osv.orm import setup_modifiers
from openerp.tools.safe_eval import safe_eval as eval
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
import time


# Can't just override state field since it's using deprecated field function
# TODO: find a way to override state without inheriting the whole model
class stock_picking(osv.Model):
    _inherit = 'stock.picking'

    def _get_pickings(self, cr, uid, ids, context=None):
        res = set()
        for move in self.browse(cr, uid, ids, context=context):
            if move.picking_id:
                res.add(move.picking_id.id)
        return list(res)

    def _state_get(self, cr, uid, ids, fieldname, arg, context=None):
        '''The state of a picking depends on the state of its related stock.move
            draft: the picking has no line or any one of the lines is draft
            done, draft, cancel: all lines are done / draft / cancel
            transit: all lines are transit or cancel and at least one is transit
            confirmed, waiting, assigned, partially_available depends on move_type (all at once or partial)
        '''
        traveled = []
        res = {}
        for pick in self.browse(cr, uid, ids, context=context):
            if not pick.move_lines:
                res[pick.id] = pick.launch_pack_operations and 'assigned' or 'draft'
                continue
            if any([x.state == 'draft' for x in pick.move_lines]):
                res[pick.id] = 'draft'
                continue
            if all([x.state == 'cancel' for x in pick.move_lines]):
                res[pick.id] = 'cancel'
                continue
            if all([x.state in ('cancel', 'done') for x in pick.move_lines]):
                res[pick.id] = 'done'
                continue
            if any([x.state == 'transit' for x in pick.move_lines]):
                res[pick.id] = 'transit'
                # traveled.append(pick.id)
                continue
            if all([x.state == 'processed' for x in pick.move_lines]):
                res[pick.id] = 'processed'
                # traveled.append(pick.id)
                continue
            if all([x.state == 'undelivered' for x in pick.move_lines]):
                res[pick.id] = 'undelivered'
                continue
                # traveled.append(pick.id)
            order = {'confirmed': 0, 'waiting': 1, 'assigned': 2, 'processed': 3}
            order_inv = {0: 'confirmed', 1: 'waiting', 2: 'assigned', 3: 'processed'}
            lst = [order[x.state] for x in pick.move_lines if
                   x.state not in ('cancel', 'done')]
            if pick.move_type == 'one':
                res[pick.id] = order_inv[min(lst)]
            else:
                # we are in the case of partial delivery, so if all move are assigned, picking
                # should be assign too, else if one of the move is assigned, or partially available, picking should be
                # in partially available state, otherwise, picking is in waiting or confirmed state
                res[pick.id] = order_inv[max(lst)]
                if not all(x == 2 for x in lst):
                    if any(x == 2 for x in lst):
                        res[pick.id] = 'partially_available'
                    else:
                        # if all moves aren't assigned, check if we have one product partially available
                        for move in pick.move_lines:
                            if move.partially_available:
                                res[pick.id] = 'partially_available'
                                break

        return res

    _columns = {
        'state': Fields.function(_state_get, type="selection", copy=False,
                                 store={
                                     'stock.picking': (
                                         lambda self, cr, uid, ids, ctx: ids, ['move_type', 'launch_pack_operations'],
                                         20),
                                     'stock.move': (_get_pickings, ['state', 'picking_id', 'partially_available'], 20)},
                                 selection=[
                                     ('draft', 'Draft'),
                                     ('cancel', 'Cancelled'),
                                     ('waiting', 'Waiting Another Operation'),
                                     ('confirmed', 'Waiting Availability'),
                                     ('partially_available', 'Partially Available'),
                                     ('assigned', 'Available'),
                                     ('processed', 'Processed'),
                                     ('transit', 'Transit'),
                                     ('undelivered', 'Undelivered'),
                                     ('done', 'Done'),
                                 ], string='Status', readonly=True, select=True, track_visibility='onchange',
                                 help="""
            * Draft: not confirmed yet and will not be scheduled until confirmed\n
            * Waiting Another Operation: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n
            * Waiting Availability: still waiting for the availability of products\n
            * Partially Available: some products are available and reserved\n
            * Ready to Transfer: products reserved, simply waiting for confirmation.\n
            * Transferred: has been processed, can't be modified or cancelled anymore\n
            * Transit: display when do HQ internal transfer, waiting for logistics to confirm\n
            * Cancelled: has been cancelled, can't be confirmed anymore"""
                                 ),
    }


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    request_id = fields.Many2one(comodel_name='br.stock.request.transfer', string="Transfer Request", index=True, ondelete='restrict')
    is_logistic_cancel = fields.Boolean(string="Is Logistic Cancel", default=False, copy=False)
    date_order = fields.Datetime(related='request_id.date_order', store=True, readonly=1)
    expected_date = fields.Datetime(related='request_id.expected_date', store=True, readonly=1)
    received_date = fields.Datetime(string="Received Date")
    # Outlet information
    outlet_id = fields.Many2one(comodel_name='br_multi_outlet.outlet', related='request_id.outlet_id', store=True)
    outlet_area_id = fields.Many2one(comodel_name='res.country.state', related='outlet_id.state_id', store=True)
    outlet_area_code = fields.Char(related='outlet_area_id.code', store=True, readonly=1)
    outlet_area_mng_id = fields.Many2one(comodel_name='res.users', related='outlet_id.area_manager', store=True)
    outlet_route_id = fields.Many2one(comodel_name='br.outlet.route', related='outlet_id.route_id', store=True)

    schedule_expected_diff = fields.Integer(string="Schedule & Expected Time Diff", compute='_get_schedule_expected_diff', search='_search_schedule_expected_diff', store=True)
    allow_dispute = fields.Boolean(string="Allow Dispute", compute='_get_allow_dispute')
    auto_transit_failed = fields.Boolean(string="Is Auto Transit Failed", default=False)
    auto_transit_log = fields.Text(string=_("Auto Transit Log"))
    requested_move_lines = fields.One2many(string="Move Lines", comodel_name='stock.move', related='move_lines')
    hide_mark_validate_button = fields.Boolean(string='Hide Mark As Todo/ Validate Button', compute='_get_hide_button')
    show_cancel_button = fields.Boolean(string='Show Cancel Button', compute='_get_show_cancel_button', default=True)

    requested_pack_operation_product_ids = fields.One2many(string="Our Operations", comodel_name='stock.pack.operation'
                                                           , states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}
                                                           , related='pack_operation_product_ids')
    damaged_moved_lines_related = fields.One2many('stock.move',
                                                  related='move_lines',
                                                  readonly=False,
                                                  string="Damaged Stock Moves",
                                                  copy=False)

    @api.multi
    def _get_show_cancel_button(self):
        """
        Show the Cancel button in Draft, Confirmed and Waiting state.
        Make the Cancel button visible to certain group in Assigned, Partially Available, Transit and Processed state.
        Hide the Cancel button in Done, Cancelled and Undelivered state.
        :return:
        """
        user = self.env.user
        for picking in self:
            if picking.state in ('draft', 'confirmed', 'waiting'):
                picking.show_cancel_button = True
            elif picking.state in ('assigned', 'partially_available', 'processed', 'transit'):
                if user.has_group('base.stock_picking_cancellation_group'):
                    picking.show_cancel_button = True
                else:
                    picking.show_cancel_button = False
            else:
                picking.show_cancel_button = False

    @api.multi
    def _get_hide_button(self):
        """
        Only allow the user in transfer validation group to perform validation in outlet ordering
        :return:
        """
        user = self.env.user
        for picking in self:
            if picking.request_id and not user.has_group('base.stock_picking_validation_group'):
                picking.hide_mark_validate_button = True
            else:
                picking.hide_mark_validate_button = False

    @api.depends('date_done')
    @api.multi
    def _get_allow_dispute(self):
        """
        Can only raise dispute within 24 hours starting from system validation time
        :return:
        """
        picking_obj = self.env['stock.picking']
        now = datetime.now()
        for picking in self:
            if picking_obj.search([('picking_orig_id', '=', picking.id), ('is_dispute_picking', '=', True)]):
                picking.allow_dispute = False
                continue
            if self.env.user.has_group('br_stock_request.stock_picking_raise_dispute_group'):
                picking.allow_dispute = True
                continue
            date_done = picking.date_done
            if not date_done:
                picking.allow_dispute = True
                continue
            if isinstance(date_done, str) or isinstance(date_done, unicode):
                date_done = datetime.strptime(picking.date_done, DEFAULT_SERVER_DATETIME_FORMAT)
            diff = (now - date_done).total_seconds()
            picking.allow_dispute = diff < 86400

    def _prepare_values_extra_move(self, cr, uid, op, product, remaining_qty, context=None):
        res = super(stock_picking, self)._prepare_values_extra_move(cr, uid, op, product, remaining_qty, context=context)
        if op.linked_move_operation_ids and op.linked_move_operation_ids[0].move_id.request_line_id:
            res.update(request_line_id=op.linked_move_operation_ids[0].move_id.request_line_id.id)
        return res

    @api.depends('expected_date', 'min_date')
    @api.multi
    def _get_schedule_expected_diff(self):
        """

        :return: (Float) Time difference in days
        """
        for sp in self:
            if not sp.expected_date and not sp.min_date:
                diff = 0
            elif not sp.expected_date:
                diff = -1
            elif not sp.min_date:
                diff = 1
            else:
                expected_date, min_date = sp.expected_date, sp.min_date
                if isinstance(sp.expected_date, str):
                    expected_date = datetime.strptime(sp.expected_date, DEFAULT_SERVER_DATETIME_FORMAT)
                if isinstance(sp.min_date, str):
                    min_date = datetime.strptime(sp.min_date, DEFAULT_SERVER_DATETIME_FORMAT)
                diff = (expected_date.date() - min_date.date()).total_seconds() / 86400
            sp.schedule_expected_diff = diff

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockPicking, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                           submenu=submenu)
        doc = etree.XML(result['arch'])
        exception_words = {'true': 'True', 'false': 'False'}
        for node in doc.xpath("//button[@name='do_new_transfer']"):
            attrib = eval(str(node.attrib))
            key = 'attrs' if 'attrs' in attrib else 'modifiers'
            if key in attrib:
                for w in exception_words:
                    attrib[key] = attrib[key].replace(w, exception_words[w])
                attrs = eval(attrib[key])
                if 'invisible' in attrs and not isinstance(attrs['invisible'], bool):
                    invisible_rule = attrs['invisible']
                    invisible_rule[0:0] = ['|', ('request_id', '!=', False)]
                    attrs['invisible'] = invisible_rule
                    node.set('attrs', str(attrs))
                    setup_modifiers(node)

        # Hide all stock move that doesn't have requet_id
        for f in ['move_lines', 'move_lines_related', 'damaged_moved_lines_related']:
            for node in doc.xpath("//field[@name='%s']" % f):
                attrib = eval(str(node.attrib))
                key = 'attrs' if 'attrs' in attrib else 'modifiers'
                if key in attrib:
                    for w in exception_words:
                        attrib[key] = attrib[key].replace(w, exception_words[w])
                    attrs = eval(attrib[key])
                    if 'invisible' in attrs and not isinstance(attrs['invisible'], bool):
                        invisible_rule = attrs['invisible']
                        invisible_rule[0:0] = ['|', ('request_id', '!=', False)]
                        attrs['invisible'] = invisible_rule
                        node.set('attrs', str(attrs))
                        setup_modifiers(node)

        result['arch'] = etree.tostring(doc)
        return result

    def do_new_transit(self, cr, uid, ids, context=None):
        pack_op_obj = self.pool['stock.pack.operation']
        data_obj = self.pool['ir.model.data']
        for pick in self.browse(cr, uid, ids, context=context):
            to_delete = []
            if not pick.move_lines and not pick.pack_operation_ids:
                raise UserError(_('Please create some Initial Demand or Mark as Todo and create some Operations.'))
            if pick.state == 'assigned' and pick.request_id:
                diff_product_msg = ""
                for pack_line in pick.pack_operation_product_ids:
                    diff = sum([x.qty_done for x in pick.pack_operation_product_ids.filtered(lambda x: x.product_id.id == pack_line.product_id.id)]) \
                            - sum([x.request_ordered_qty for x in pick.move_lines.filtered(lambda x: x.product_id.id == pack_line.product_id.id)])
                    if diff > 0 and diff < 1:
                        diff_product_msg += '%s - diff (%s)\n'%(pack_line.product_id.name, diff)

                if diff_product_msg:
                    raise ValidationError("Bellow Products Quantity does not match in Operations tab and Initial Demand tab.\n"
                                          "Please update the Done quantity for this product in "
                                          "Operations tab before validating stock operations. \n\n %s"%(diff_product_msg))

            # In draft or with no pack operations edited yet, ask if we can just do everything
            if pick.state == 'draft' or all([x.qty_done == 0.0 for x in pick.pack_operation_ids]):
                # If no lots when needed, raise error
                picking_type = pick.picking_type_id
                if picking_type.use_create_lots or picking_type.use_existing_lots:
                    for pack in pick.pack_operation_ids:
                        if pack.product_id and pack.product_id.tracking != 'none':
                            raise UserError(_('Some products require lots, so you need to specify those first!'))
                view = data_obj.xmlid_to_res_id(cr, uid, 'stock.view_immediate_transfer')
                wiz_id = self.pool['stock.immediate.transfer'].create(cr, uid, {'pick_id': pick.id}, context=context)
                return {
                    'name': _('Immediate Transfer?'),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.immediate.transfer',
                    'views': [(view, 'form')],
                    'view_id': view,
                    'target': 'new',
                    'res_id': wiz_id,
                    'context': context,
                }
            for operation in pick.pack_operation_ids:
                if operation.lots_visible:
                    has_lot = self.pool['stock.pack.operation.lot'].search(
                        cr, uid, [('operation_id', '=', operation.id)], limit=1)
                    if not has_lot:
                        raise ValidationError(
                            _('Some products require Lot/Expiry Date, so you need to specify those first!'))

                if operation.qty_done < 0:
                    raise UserError(_('No negative quantities allowed'))
                if operation.qty_done > 0:
                    pack_op_obj.write(cr, uid, operation.id, {'product_qty': operation.qty_done}, context=context)
                else:
                    to_delete.append(operation.id)
            if to_delete:
                pack_op_obj.unlink(cr, uid, to_delete, context=context)


            # Check backorder should check for other barcodes
            if self.check_backorder(cr, uid, pick, context=context):
                view = data_obj.xmlid_to_res_id(cr, uid, 'stock.view_backorder_confirmation')
                wiz_id = self.pool['stock.backorder.confirmation'].create(cr, uid, {'pick_id': pick.id},
                                                                          context=context)
                return {
                    'name': _('Create Backorder?'),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'stock.backorder.confirmation',
                    'views': [(view, 'form')],
                    'view_id': view,
                    'target': 'new',
                    'res_id': wiz_id,
                    'context': context,
                }
        self.do_process_transfer(cr, uid, ids, context=context)
        return

    @api.multi
    def do_transit(self):
        for picking in self:
            if picking.picking_orig_id:
                picking.request_id.write({'closed_time': datetime.now()})
            moves = picking.move_lines.filtered(lambda x: x.state == 'processed')
            moves.write({'state': 'transit'})

    @api.multi
    def do_process_transfer(self):
        for picking in self:
            picking.with_context(split_to_backorder=True).do_split()
            moves = picking.move_lines
            # Reserve quant for confirmed moves
            to_assign = moves.filtered(lambda x: x.state == 'confirmed')
            if to_assign:
                to_assign.action_assign()
            for move in moves:
                if move.state == 'assigned':
                    if not picking.picking_orig_id:
                        request_line = move.request_line_id
                        request_line.write({'committed_qty': request_line.committed_qty + move._get_request_uom_qty()})
            moves.write({'state': 'processed'})
        return True

    @api.multi
    def do_process_transfer_done(self):
        """Update delivered quantity"""
        for picking in self:
            picking.picking_recompute_remaining_quantities(picking)
            to_dos = picking.move_lines.filtered(lambda x: x.state == 'transit')
            to_dos.action_done()
            for move in to_dos:
                request_line = move.request_line_id
                if move.picking_id.backorder_id:
                    delivered_qty = request_line.delivered_qty + move._get_request_uom_qty()
                elif move.picking_id.picking_orig_id:
                    dispute_picking_type = self.env.ref('br_stock_request.br_dispute_picking_type').id
                    if picking.picking_type_id.id == dispute_picking_type:
                        delivered_qty = request_line.delivered_qty + move._get_request_uom_qty()
                    else:
                        delivered_qty = request_line.delivered_qty - move._get_request_uom_qty()
                else:
                    delivered_qty = move._get_request_uom_qty()
                request_line.write({'delivered_qty': delivered_qty})
            picking.write({'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

    @api.multi
    def action_cancel(self):
        to_drops = self.env['stock.picking']
        # logistic_group = self.env.ref('br_stock_request.group_inventory_pic', None) or self.env['res.groups']
        # is_logistic = logistic_group.id in self.env.user.groups_id.ids
        is_logistic = self.request_id.requestor_id.id == self.env.user.id if self.request_id else False
        if is_logistic:
            for picking in self:
                if picking.request_id:
                    picking.write({'is_logistic_cancel': True})
                    if picking.state == 'transit':
                        to_drops |= picking
        res = super(StockPicking, self).action_cancel()
        for d in to_drops:
            d.move_lines.write({'state': 'undelivered'})
        return res

    @api.multi
    def raise_dispute(self):
        self.ensure_one()
        view = self.env.ref('br_stock_request.view_stock_transfer_dispute_form').id
        return {
            'name': _('Raise Dipute'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.transfer.dispute',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'context': {'active_id': self.id},
        }


class StockMove(models.Model):
    _inherit = "stock.move"

    request_line_id = fields.Many2one(comodel_name='br.stock.request.transfer.line', string="Transfer Line", index=True)
    state = fields.Selection(
        selection_add=[('processed', 'Processed'), ('transit', 'Transit'), ('undelivered', 'Undelivered')])
    request_expected_date = fields.Datetime(related='request_id.expected_date')
    request_date_order = fields.Datetime(related='request_id.date_order')
    request_ordered_qty = fields.Float(related='request_line_id.ordered_qty')
    remark_id = fields.Many2one(comodel_name='stock.picking.remark',
                                string="Damage Reason", ondelete='restrict')
    is_damage_move = fields.Boolean(related='picking_id.to_damage_location', string='Damage Move')

    def _get_request_uom_qty(self):
        if not self.request_line_id:
            request_uom = self.product_uom
        else:
            request_uom = self.request_line_id.uom_id
        return self.env['product.uom']._compute_qty_obj(self.product_uom, self.product_uom_qty,
                                                        request_uom)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockMove, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                           submenu=submenu)

        if self.env.context.get('no_create', False) and self.env.context.get('no_delete', False):
            doc = etree.XML(result['arch'])
            for node in doc.xpath("//tree"):
                node.set('create', 'false')
                node.set('delete', 'false')
                setup_modifiers(node)
            for node in doc.xpath("//field[@name='product_id']"):
                attrib = eval(str(node.attrib))
                key = 'attrs' if 'attrs' in attrib else 'modifiers'
                if key in attrib:
                    exception_words = {'true': 'True', 'false': 'False'}
                    for w in exception_words:
                        attrib[key] = attrib[key].replace(w, exception_words[w])
                    attrs = eval(attrib[key])
                    if 'readonly' in attrs and not isinstance(attrs['readonly'], bool):
                        readonly_rule = attrs['readonly']
                        readonly_rule[0:0] = ['|', ('request_line_id', '!=', False)]
                        attrs['readonly'] = readonly_rule
                        attrs_str = str(attrs)
                        node.set('attrs', attrs_str)
                        setup_modifiers(node)
            result['arch'] = etree.tostring(doc)
        return result


class StockPackOperation(models.Model):
    _inherit = "stock.pack.operation"

    state = fields.Selection(selection_add=[('processed', 'Processed'), ('transit', 'Transit'), ('undelivered', 'Undelivered')])
    picking_id = fields.Many2one('stock.picking', 'Stock Picking', help='The stock operation where the packing has been made', required=False)

