from openerp import fields, api, models, _
from openerp.tools.float_utils import float_compare, float_round
from openerp.exceptions import UserError
from openerp.exceptions import ValidationError
import time
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

class StockPickingRemark(models.Model):
    _name = 'stock.picking.remark'

    name = fields.Char(string="Damage Reason", required=True)
    active = fields.Boolean(string="Active", default=True)


class stock_picking(models.Model):
    _inherit = 'stock.picking'

    driver = fields.Many2one(string='Driver', comodel_name='res.partner', domain=[('type', '=', 'driver')], ondelete='restrict')
    packer = fields.Many2one(string="Picker/Packer", comodel_name='res.partner', domain=[('type', '=', 'picker_packer')], ondelete='restrict')
    vehicle = fields.Many2one(string='Vehicle', comodel_name='br.fleet.vehicle', ondelete='restrict')
    location_usage = fields.Selection(related='location_id.usage', readonly=True, store=True, string="Source Location Usage")
    remark_id = fields.Many2one(comodel_name='stock.picking.remark', string="Damage Reason", ondelete='restrict')
    to_damage_location = fields.Boolean(compute='_check_to_damage_location', store=True)
    warehouse_id = fields.Many2one(comodel_name='stock.warehouse', string="Location Warehouse", compute='_get_warehouse_id', store=True)
    dest_warehouse_id = fields.Many2one(comodel_name='stock.warehouse', string="Destination Location Warehouse", compute='_get_warehouse_id', store=True)
    is_destination_change = fields.Boolean('Is Destination Location Change')

    @api.one
    def copy(self, default=None):
        return super(stock_picking, self.with_context(copy_picking=True)).copy(default=default)

    @api.model
    def create(self, vals):
        res = super(stock_picking, self).create(vals)
        if 'is_destination_change' in vals.keys() and not self.env.context.get('copy_picking'):
            res.update_location_dest_id()
        return res

    @api.multi
    def write(self, vals):
        res = super(stock_picking, self).write(vals)
        if 'location_dest_id' in vals.keys() and 'is_destination_change' in vals.keys():
            self.update_location_dest_id()
        return res

    # FIXME: This should be on change.
    # but due to onchange is not working on staging so i have to do some outof box with is_destination_change extra boolean field.
    # Honestly its an dumb solution but due to urgency i need to fix it with this approach first.
    @api.multi
    def update_location_dest_id(self):
        """
        Set analytic account for all stock.move lines when event onchange of location_dest_id triggered
        """
        for picking in self:
            if picking.location_dest_id:
                analytic_account_id = picking.location_dest_id.get_analytic_account()
                for move in picking.move_lines:
                    move.account_analytic_id = analytic_account_id
            else:
                for move in picking.move_lines:
                    move.account_analytic_id = False

    @api.onchange('location_dest_id')
    def onchange_location_dest_id(self):
        self.is_destination_change = not self.is_destination_change




    @api.depends('location_id', 'location_dest_id')
    @api.multi
    def _get_warehouse_id(self):
        for sp in self:
            sp.warehouse_id = sp.location_id.get_warehouse(sp.location_id)
            sp.dest_warehouse_id = sp.location_dest_id.get_warehouse(sp.location_dest_id)

    @api.depends('location_dest_id')
    @api.multi
    def _check_to_damage_location(self):
        for p in self:
            p.to_damage_location = p.location_dest_id.damage_location

    def _prepare_values_extra_move(self, cr, uid, op, product, remaining_qty, context=None):
        res = super(stock_picking, self)._prepare_values_extra_move(cr, uid, op, product, remaining_qty, context=context)
        if op.linked_move_operation_ids and op.linked_move_operation_ids[0].move_id.account_analytic_id:
            res.update(account_analytic_id=op.linked_move_operation_ids[0].move_id.account_analytic_id.id)
        return res

    def rereserve_quants(self, cr, uid, picking, move_ids=[], context=None):
        """ Unreserve quants then try to reassign quants."""

        if context is None:
            context = {}
        stock_move_obj = self.pool.get('stock.move')
        if not move_ids:
            self.do_unreserve(cr, uid, [picking.id], context=context)
            self.action_assign(cr, uid, [picking.id], context=context)
        else:
            if 'no_state_change' in context:
                move = stock_move_obj.browse(cr, uid, move_ids, context=context)
                stock_move_obj.do_unreserve(cr, uid, [m.id for m in move if m.reserved_quant_ids], context=context)
            else:
                stock_move_obj.do_unreserve(cr, uid, move_ids, context=context)
                stock_move_obj.action_assign(cr, uid, move_ids, no_prepare=True, context=context)

    def action_assign(self, cr, uid, ids, context=None):
        context = context or {}
        super(stock_picking, self).action_assign(cr, uid, ids, context)
        pickings = self.browse(cr, uid, ids, context=context)
        for picking in pickings:
            if picking.state in ('partially_available', 'assigned'):
                self.do_prepare_partial(cr, uid, [picking.id], context=context)
        for picking in pickings:
            # when user click on reserve button or confirm SO
            # validate the operation tab
            # must have operation line if there is available initial demand
            if any(move.state == 'assigned' for move in picking.requested_move_lines):
                if not picking.requested_pack_operation_product_ids:
                    raise UserError(_(
                        "There is currently no stock for the products being "
                        "reserved, please ensure there is stock prior to "
                        "clicking the Reserve button."
                    ))

    def _check_group_by_vendor(self, picking):
        return True

    def _create_backorder(self, cr, uid, picking, backorder_moves=[], context=None):
        """ Move all non-done lines into a new backorder picking. If the key 'do_only_split' is given in the context, then move all lines not in context.get('split', []) instead of all non-done lines.
        """

        if not backorder_moves:
            backorder_moves = picking.move_lines
        states = ['done', 'cancel']
        # Longdt: Allow create backorder even if split move only
        if context.get('split_to_backorder', False):
            states.extend(['assigned', 'processed', 'transit'])
            # fix don't get move with quantity = 0 to backorder
            backorder_move_ids = [x.id for x in backorder_moves if x.state not in states
                                  and x.split_from and x.split_from.picking_id.id == picking.id
                                  and x.product_qty > 0
                                  or (x.state == 'confirmed' and x.product_qty > 0 and x.id not in context.get('split', []))
                                  or (x.state == 'assigned' and x.product_qty > 0 and len(x.linked_move_operation_ids) == 0)]
        else:
            backorder_move_ids = [x.id for x in backorder_moves if x.state not in states]
            if 'do_only_split' in context and context['do_only_split']:
                backorder_move_ids = [x.id for x in backorder_moves if x.id not in context.get('split', [])]

        if backorder_move_ids:
            backorder_id = self.copy(cr, uid, picking.id, {
                'name': '/',
                'move_lines': [],
                'pack_operation_ids': [],
                'backorder_id': picking.id,
            })
            backorder = self.browse(cr, uid, backorder_id, context=context)
            self.message_post(cr, uid, picking.id, body=_("Back order <em>%s</em> <b>created</b>.") % (backorder.name), context=context)
            move_obj = self.pool.get("stock.move")
            move_obj.write(cr, uid, backorder_move_ids, {'picking_id': backorder_id}, context=context)

            if not picking.date_done:
                self.write(cr, uid, [picking.id], {'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
            self.action_confirm(cr, uid, [backorder_id], context=context)
            self.action_assign(cr, uid, [backorder_id], context=context)
            return backorder_id
        return False

    def _prepare_pack_ops(self, cr, uid, picking, quants, forced_qties, context=None):
        """ override
        """

        def _picking_putaway_apply(product):
            location = False
            # Search putaway strategy
            if product_putaway_strats.get(product.id):
                location = product_putaway_strats[product.id]
            else:
                location = self.pool.get('stock.location').get_putaway_strategy(cr, uid, picking.location_dest_id, product, context=context)
                product_putaway_strats[product.id] = location
            return location or picking.location_dest_id.id

        group_by_vendor = self._check_group_by_vendor(picking)
        # If we encounter an UoM that is smaller than the default UoM or the one already chosen, use the new one instead.
        product_uom = {}  # Determines UoM used in pack operations
        location_dest_id = None
        location_id = None
        for move in [x for x in picking.move_lines if x.state not in ('done', 'cancel')]:
            if not product_uom.get(move.product_id.id):
                product_uom[move.product_id.id] = move.product_uom
            if move.product_uom.id != move.product_id.uom_id.id and move.product_uom.factor > product_uom[move.product_id.id].factor:
                product_uom[move.product_id.id] = move.product_uom
            if not move.scrapped:
                if location_dest_id and move.location_dest_id.id != location_dest_id:
                    raise UserError(_('The destination location must be the same for all the moves of the picking.'))
                location_dest_id = move.location_dest_id.id
                if location_id and move.location_id.id != location_id:
                    raise UserError(_('The source location must be the same for all the moves of the picking.'))
                location_id = move.location_id.id
        location = self.pool.get('stock.location').browse(cr, uid, location_id, context=context)
        pack_obj = self.pool.get("stock.quant.package")
        quant_obj = self.pool.get("stock.quant")
        vals = []
        qtys_grouped = {}
        lots_grouped = {}
        # for each quant of the picking, find the suggested location
        quants_suggested_locations = {}
        product_putaway_strats = {}
        for quant in quants:
            if quant.qty <= 0:
                continue
            suggested_location_id = _picking_putaway_apply(quant.product_id)
            quants_suggested_locations[quant] = suggested_location_id

        # find the packages we can move as a whole
        top_lvl_packages = self._get_top_level_packages(cr, uid, quants_suggested_locations, context=context)
        # and then create pack operations for the top-level packages found
        for pack in top_lvl_packages:
            pack_quant_ids = pack_obj.get_content(cr, uid, [pack.id], context=context)
            pack_quants = quant_obj.browse(cr, uid, pack_quant_ids, context=context)

            vals.append({
                'picking_id': picking.id,
                'package_id': pack.id,
                'product_qty': 1.0,
                'location_id': pack.location_id.id,
                'location_dest_id': quants_suggested_locations[pack_quants[0]],
                'owner_id': pack.owner_id.id,
                'vendor_id': pack_quants[0].vendor_id.id if pack_quants[0].vendor_id else False
            })
            # remove the quants inside the package so that they are excluded from the rest of the computation
            for quant in pack_quants:
                del quants_suggested_locations[quant]
        # Go through all remaining reserved quants and group by product, package, owner, source location and dest location
        # Lots will go into pack operation lot object
        for quant, dest_location_id in quants_suggested_locations.items():
            vendor = quant.vendor_id
            if not vendor:
                supplier = quant.product_id.product_tmpl_id.get_supplier()
                vendor = supplier.name if supplier else False
            key = (quant.product_id.id, quant.package_id.id, quant.owner_id.id, quant.location_id.id, dest_location_id, vendor.id if vendor else False)
            if qtys_grouped.get(key):
                qtys_grouped[key] += quant.qty
            else:
                qtys_grouped[key] = quant.qty
            if group_by_vendor and quant.lot_id:
                lots_grouped.setdefault(key, {}).setdefault(quant.lot_id.id, 0.0)
                lots_grouped[key][quant.lot_id.id] += quant.qty

        # Do the same for the forced quantities (in cases of force_assign or incomming shipment for example)
        for product, qty in forced_qties.items():
            if qty <= 0:
                continue
            # get vendor from incoming shipment
            if location.usage == 'supplier':
                vendor_id = picking.partner_id.id if picking.partner_id else False
            else:
                vendor = product.product_tmpl_id.get_default_supplier()
                vendor_id = vendor.name.id if vendor else False
            suggested_location_id = _picking_putaway_apply(product)
            key = (product.id, False, picking.owner_id.id, picking.location_id.id, suggested_location_id, vendor_id)
            if qtys_grouped.get(key):
                qtys_grouped[key] += qty
            else:
                qtys_grouped[key] = qty

        # Create the necessary operations for the grouped quants and remaining qtys
        uom_obj = self.pool.get('product.uom')
        prevals = {}
        for key, qty in qtys_grouped.items():
            product = self.pool.get("product.product").browse(cr, uid, key[0], context=context)
            uom_id = product.uom_id.id
            qty_uom = qty
            if product_uom.get(key[0]):
                uom_id = product_uom[key[0]].id
                qty_uom = uom_obj._compute_qty(cr, uid, product.uom_id.id, qty, uom_id)
            pack_lot_ids = []
            if lots_grouped.get(key):
                for lot in lots_grouped[key].keys():
                    lot_obj = self.pool.get("stock.production.lot").browse(cr, uid, lot, context=context)
                    supplier = False
                    if lot_obj.br_supplier_id:
                        supplier = lot_obj.br_supplier_id.id
                    qty_todo = uom_obj._compute_qty(cr, uid, product.uom_id.id, lots_grouped[key][lot], uom_id)
                    pack_lot_ids += [(0, 0, {'lot_id': lot,
                                             'qty': 0.0,
                                             'qty_todo': qty_todo,
                                             'br_supplier_id': supplier,
                                             'br_removal_date': lot_obj.removal_date})]
            val_dict = {
                'picking_id': picking.id,
                'product_qty': qty_uom,
                'product_id': key[0],
                'package_id': key[1],
                'owner_id': key[2],
                'location_id': key[3],
                'location_dest_id': key[4],
                'product_uom_id': uom_id,
                'pack_lot_ids': pack_lot_ids,
                'vendor_id': key[5]
            }
            if key[0] in prevals:
                prevals[key[0]].append(val_dict)
            else:
                prevals[key[0]] = [val_dict]
        # prevals var holds the operations in order to create them in the same order than the picking stock moves if possible
        processed_products = set()
        for move in [x for x in picking.move_lines if x.state not in ('done', 'cancel')]:
            if move.product_id.id not in processed_products:
                pvals = prevals.get(move.product_id.id, [])
                for item in pvals:
                    qty_done = 0
                    move_qty = item['product_qty']
                    # change qty_todo to move's product_uom_qty
                    for lot in item['pack_lot_ids']:
                        lot[2].update(
                            qty=lot[2]['qty_todo'],
                        )
                        qty_done += lot[2]['qty_todo']
                    # Update uom and quantity reserved
                    item.update(
                        qty_done=qty_done if move.product_id.tracking == 'lot' and move.location_dest_id.damage_location else move_qty
                    )
                vals += pvals
                processed_products.add(move.product_id.id)
        return vals

    def check_backorder(self, cr, uid, picking, context=None):
        need_rereserve, all_op_processed = self.picking_recompute_remaining_quantities(cr, uid, picking, done_qtys=True, context=context)
        for move in picking.move_lines:
            if move.state != 'cancel' and float_compare(move.remaining_qty, 0, precision_rounding=move.product_id.uom_id.rounding) != 0:
                return True
        return False
    
    @api.multi
    def check_order_qty_more(self):
        po_obj = self.env['purchase.order']
        for pick in self:
            if pick.origin:
                po = po_obj.search([('name','=',pick.origin)])
                po_product_qty = {}
                if po:
                    for po_line in po.order_line:
                        if po_line.product_id.id not in po_product_qty:
                            po_product_qty[po_line.product_id.id] = 0
                        po_product_qty[po_line.product_id.id] += po_line.product_qty
                picking_product_qty = {}
                for operation_line in pick.pack_operation_product_ids:
                    if operation_line.product_id.id not in picking_product_qty:
                        picking_product_qty[operation_line.product_id.id] = 0
                    picking_product_qty[operation_line.product_id.id] += operation_line.qty_done
                
                max_qty_product_ids = []
                for key,value in picking_product_qty.iteritems():
                    if key in po_product_qty.keys() and po_product_qty[key] < value:
                        max_qty_product_ids.append(key)
                if max_qty_product_ids:
                    raise UserError(_('You are trying to receive product more then ordered. Please contact your manager !'))
        
    def do_new_transfer(self, cr, uid, ids, context=None):
        pack_op_obj = self.pool['stock.pack.operation']
        data_obj = self.pool['ir.model.data']
        
        if not self.pool['res.users'].browse(cr, uid, uid, context=context).has_group('base.allow_receive_more_quantity'):
            self.check_order_qty_more(cr, uid, ids, context=context)
            
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.state == 'done':
                raise UserError(_('You are trying to validate Picking - %s which is already validated ! '%(pick.name)))
            to_delete = []
            if not pick.move_lines and not pick.pack_operation_ids:
                raise UserError(_('Please create some Initial Demand or Mark as Todo and create some Operations. '))
            # In draft or with no pack operations edited yet, ask if we can just do everything
            if pick.state == 'draft' or all([x.qty_done == 0.0 for x in pick.pack_operation_ids]):
                # If no lots when needed, raise error
                picking_type = pick.picking_type_id
                if (picking_type.use_create_lots or picking_type.use_existing_lots):
                    for pack in pick.pack_operation_ids:
                        if pack.product_id and pack.product_id._check_need_tracking(pack):
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
            for operation in pick.pack_operation_ids:
                if operation.qty_done < 0:
                    raise UserError(_('No negative quantities allowed'))
                if operation.qty_done > 0:
                    pack_op_obj.write(cr, uid, operation.id, {'product_qty': operation.qty_done}, context=context)
                else:
                    to_delete.append(operation.id)
            if to_delete:
                pack_op_obj.unlink(cr, uid, to_delete, context=context)
        self.do_transfer(cr, uid, ids, context=context)
        return

    def do_transfer(self, cr, uid, ids, context=None):
        for pick in self.browse(cr, uid, ids, context=context):
            if not pick.pack_operation_ids or len(pick.pack_operation_ids) <= 0:
                raise ValidationError(
                    _(
                        "Please check ordered quantity for all products because all quantities are 0"))
        return super(stock_picking, self).do_transfer(cr, uid, ids, context=context)

    def action_confirm(self, cr, uid, ids, context=None):
        todo = []
        todo_force_assign = []
        for picking in self.browse(cr, uid, ids, context=context):
            if not picking.move_lines:
                self.launch_packops(cr, uid, [picking.id], context=context)
            if picking.location_id.usage in ('supplier', 'inventory', 'production') \
                    or (picking.location_dest_id.usage in ('inventory') and picking.location_dest_id.scrap_location == True)\
                    or (picking.transfer_direction == 'outlet_outlet') or (len(picking.location_id.warehouse_id.outlet_ids) > 0
                    and picking.location_dest_id.usage == 'transit') or picking.is_dispute_picking:  # If destination location is damage location or direction is from outlet to outlet OR from outlet to transit, then force assign too
                todo_force_assign.append(picking.id)
            for r in picking.move_lines:
                if r.state == 'draft':
                    todo.append(r.id)
        if len(todo):
            self.pool.get('stock.move').action_confirm(cr, uid, todo, context=context)

        if todo_force_assign:
            self.force_assign(cr, uid, todo_force_assign, context=context)
        return True


class ResPartner(models.Model):
    _inherit = 'res.partner'

    type = fields.Selection(selection_add=[('driver', 'Driver'), ('picker_packer', 'Picker / Packer')])
