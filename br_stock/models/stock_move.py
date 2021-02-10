from openerp.osv import osv
from openerp import models, api, fields, SUPERUSER_ID, _
from openerp.exceptions import UserError, ValidationError
from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT
import time
from collections import OrderedDict


class StockMove_NewApi(models.Model):
    _inherit = 'stock.move'

    inventory_line_id = fields.Many2one(comodel_name='stock.inventory.line')
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')], track_visibility='always', copy=True)

    @api.multi
    @api.depends('product_id')
    def _compute_vendor_uom_count(self):
        for m in self:
            if m.product_id:
                found = 0
                for vendor in m.product_id.seller_ids:
                    if len(vendor.uom_ids) > 0:
                        found = 1
                        break
                m.vendor_uom_count = found

    @api.multi
    @api.onchange('product_id')
    def onchange_product_id(self, pro_id, loc_id, loc_dest_id, partner_id):
        """
        Get analytic account for stock.move when event onchange on product_id is triggered
        """
        result = super(StockMove_NewApi, self).onchange_product_id(pro_id, loc_id, loc_dest_id, partner_id) or {}
        result.setdefault('value', {})
        if 'default_location_dest_id' in self.env.context and self.env.context['default_location_dest_id']:
            des_location = self.env['stock.location'].browse(self.env.context['default_location_dest_id'])
            analytic_account_id = des_location.get_analytic_account()
            if analytic_account_id:
                result['value']['account_analytic_id'] = analytic_account_id
        return result

    @api.constrains('product_uom')
    def _check_uom_constrain(self):
        for move in self:
            if self.product_id.uom_id.category_id.id != self.product_uom.category_id.id:
                raise ValidationError(_('You try to move a product using a UoM that is not compatible with the UoM of the product moved. Please use an UoM in the same UoM category. \n Product : %s') % self.product_id.name)




class StockMove(osv.osv):
    _inherit = 'stock.move'

    def _check_uom(self, cr, uid, ids, context=None):
        return True

    _constraints = [
        (_check_uom,
         'You try to move a product using a UoM that is not compatible with the UoM of the product moved. Please use an UoM in the same UoM category.',
         ['product_uom']),
    ]

    def write(self, cr, uid, ids, vals, context=None):
        context = context or {}
        if context.get('force_period_date'):
            vals['date'] = context.get('force_period_date')
        return super(StockMove, self).write(cr, uid, ids, vals, context=context)

    def _set_default_price_moves(self, cr, uid, moves, context=None):
        # When the cost method is in real or average price, the price can be set to 0.0 on the PO
        # So the price doesn't have to be updated
        moves = moves.filtered(lambda move: not move.price_unit and not move.product_id.cost_method in ('real', 'average'))
        return moves

    def set_default_price_unit_from_product(self, cr, uid, moves, context=None):
        """ Set price to move, important in inter-company moves or receipts with only one partner """
        context = context or {}
        for move in self._set_default_price_moves(cr, uid, moves, context=context):
            move.write({'price_unit': move.product_id.standard_price})

    # Overrided
    def product_price_update_after_done(self, cr, uid, ids, context=None):
        '''
        This method adapts the price on the product when necessary
        '''
        for move in self.browse(cr, uid, ids, context=context):
            # adapt standard price on outgoing moves if the product cost_method is 'real', so that a return
            # or an inventory loss is made using the last value used for an outgoing valuation.
            if move.product_id.cost_method == 'real' and move.location_dest_id.usage != 'internal':
                # store the average price of the move on the move and product form
                if move.location_dest_id.usage == 'transit':
                    location_pool = self.pool.get('stock.location')
                    if not location_pool.get_warehouse(cr, uid, move.location_dest_id, context=context):
                        self._store_average_cost_price(cr, uid, move, context=context)
                else:
                    self._store_average_cost_price(cr, uid, move, context=context)

    attribute_price = set_default_price_unit_from_product

    @api.cr_uid_ids_context
    def _picking_assign(self, cr, uid, move_ids, context=None):
        """Create a new picking to assign moves to.
        """
        move = self.browse(cr, uid, move_ids, context=context)[0]
        pick_obj = self.pool.get("stock.picking")
        credentials = [
            ('group_id', '=', move.group_id.id),
            ('location_id', '=', move.location_id.id),
            ('location_dest_id', '=', move.location_dest_id.id),
            ('picking_type_id', '=', move.picking_type_id.id),
            ('printed', '=', False),
            ('state', 'in', ['draft', 'confirmed', 'waiting', 'partially_available', 'assigned'])
        ]
        # Find return picking
        if move.origin_returned_move_id.picking_id:
            credentials.append(('picking_orig_id', '=', move.origin_returned_move_id.picking_id.id),)
        # Find based on origin picking
        elif move.move_orig_ids:
            credentials.append(('picking_orig_id', '=', move.move_orig_ids[0].picking_id.id), )
        picks = pick_obj.search(cr, SUPERUSER_ID, credentials, limit=1, context=context)
        if picks:
            pick = picks[0]
        else:
            values = self._prepare_picking_assign(cr, uid, move, context=context)
            values.update(picking_orig_id=move.move_orig_ids[0].picking_id.id if move.move_orig_ids else None)
            pick = pick_obj.create(cr, uid, values, context=context)
        return self.write(cr, uid, move_ids, {'picking_id': pick}, context=context)

    def check_tracking(self, cr, uid, move, ops, context=None):
        """ Checks if serial number is assigned to stock move or not and raise an error if it had to.
        """
        if move.picking_id and (move.picking_id.picking_type_id.use_existing_lots or move.picking_id.picking_type_id.use_create_lots) and \
                move.product_id._check_need_tracking(move):
            if not (move.restrict_lot_id or (ops and (ops.product_id and ops.pack_lot_ids)) or (ops and not ops.product_id)):
                raise UserError(_('You need to provide a Expiry Date Number for product %s') % move.product_id.name)

    def action_done(self, cr, uid, ids, context=None):
        """ Process completely the moves given as ids and if all moves are done, it will finish the picking.
        """
        context = context or {}
        picking_obj = self.pool.get("stock.picking")
        quant_obj = self.pool.get("stock.quant")
        uom_obj = self.pool.get("product.uom")
        todo = [move.id for move in self.browse(cr, uid, ids, context=context) if move.state == "draft"]
        if todo:
            ids = self.action_confirm(cr, uid, todo, context=context)
        pickings = set()
        procurement_ids = set()
        # Search operations that are linked to the moves
        operations = set()
        move_qty = {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.picking_id:
                pickings.add(move.picking_id.id)
            move_qty[move.id] = move.product_qty
            for link in move.linked_move_operation_ids:
                operations.add(link.operation_id)

        # Sort operations according to entire packages first, then package + lot, package only, lot only
        operations = list(operations)
        operations.sort(key=lambda x: ((x.package_id and not x.product_id) and -4 or 0) + (x.package_id and -2 or 0) + (x.pack_lot_ids and -1 or 0))

        for ops in operations:
            if ops.picking_id:
                pickings.add(ops.picking_id.id)
            entire_pack = False
            if ops.product_id:
                # If a product is given, the result is always put immediately in the result package (if it is False, they are without package)
                quant_dest_package_id = ops.result_package_id.id
            else:
                # When a pack is moved entirely, the quants should not be written anything for the destination package
                quant_dest_package_id = False
                entire_pack = True
            lot_qty = {}
            tot_qty = 0.0
            if self._check_to_pack(ops):
                for pack_lot in ops.pack_lot_ids:
                    qty = uom_obj._compute_qty(cr, uid, ops.product_uom_id.id, pack_lot.qty, ops.product_id.uom_id.id)
                    lot_qty[pack_lot.lot_id.id] = qty
                    tot_qty += pack_lot.qty
            if self._check_to_pack(ops) and ops.product_id and float_compare(tot_qty, ops.product_qty, precision_rounding=ops.product_uom_id.rounding) != 0.0:
                raise UserError(_('You have a difference between the quantity on the operation and the quantities specified for the lots. Product: %s') % ops.product_id.name_template)

            quants_taken = []
            false_quants = []
            lot_move_qty = {}
            # Group links by move first
            move_qty_ops = {}
            for record in ops.linked_move_operation_ids:
                move = record.move_id
                if not move_qty_ops.get(move):
                    move_qty_ops[move] = record.qty
                else:
                    move_qty_ops[move] += record.qty
            # Store lot in list
            pack_op_lots = list(ops.pack_lot_ids)
            pack_op_lots.sort(key=lambda k: -k.qty)
            pack_lot_qtys = OrderedDict()
            for x in pack_op_lots:
                pack_lot_qtys[x.lot_id.id] = uom_obj._compute_qty(cr, uid, ops.product_uom_id.id, x.qty, ops.product_id.uom_id.id)
            # Process every move only once for every pack operation
            move_qty_ops = OrderedDict(sorted(move_qty_ops.items(), key=lambda v: -v[0].product_qty))
            for move in move_qty_ops:
                main_domain = [('qty', '>', 0)]
                self.check_tracking(cr, uid, move, ops, context=context)
                preferred_domain = [('reservation_id', '=', move.id)]
                fallback_domain = [('reservation_id', '=', False)]
                fallback_domain2 = ['&', ('reservation_id', '!=', move.id), ('reservation_id', '!=', False)]
                if not self._check_to_pack(ops):  # ops.pack_lot_ids:
                    preferred_domain_list = [preferred_domain] + [fallback_domain] + [fallback_domain2]
                    quants = quant_obj.quants_get_preferred_domain(cr, uid, move_qty_ops[move], move, ops=ops, domain=main_domain,
                                                                   preferred_domain_list=preferred_domain_list, context=context)
                    if not ops.pack_lot_ids:
                        quant_obj.quants_move(cr, uid, quants, move, ops.location_dest_id, location_from=ops.location_id,
                                              lot_id=False, owner_id=ops.owner_id.id, src_package_id=ops.package_id.id,
                                              dest_package_id=quant_dest_package_id, entire_pack=entire_pack, context=context)
                    else:
                        new_context = context.copy()
                        new_context.update(force_lot_id=True)
                        used_quants = []
                        for lot in pack_lot_qtys:
                            total_qty = pack_lot_qtys[lot]
                            for q in quants:
                                quant, quant_qty = q
                                if quant and quant.qty and total_qty and q not in used_quants:
                                    if total_qty < quant.qty:
                                        quant_obj.quants_move(cr, uid, [(quant, quant.qty - total_qty)], move, ops.location_dest_id, location_from=ops.location_id,
                                                              lot_id=lot, owner_id=ops.owner_id.id, src_package_id=ops.package_id.id,
                                                              dest_package_id=quant_dest_package_id, entire_pack=entire_pack, context=new_context)
                                        # Lot is fully moved
                                        del pack_lot_qtys[lot]
                                        break
                                    else:
                                        total_qty -= quant.qty
                                        pack_lot_qtys[lot] = total_qty
                                        used_quants.append(q)
                                        quant_obj.quants_move(cr, uid, [(quant, quant.qty)], move, ops.location_dest_id, location_from=ops.location_id,
                                                              lot_id=lot, owner_id=ops.owner_id.id, src_package_id=ops.package_id.id,
                                                              dest_package_id=quant_dest_package_id, entire_pack=entire_pack, context=new_context)
                                        if total_qty <= 0:
                                            del pack_lot_qtys[lot]
                                # fix for case quant is none
                                if not quant and quant_qty:
                                    quant_obj.quants_move(cr, uid, [
                                        (quant, quant_qty)], move,
                                                          ops.location_dest_id,
                                                          location_from=ops.location_id,
                                                          lot_id=lot,
                                                          owner_id=ops.owner_id.id,
                                                          src_package_id=ops.package_id.id,
                                                          dest_package_id=quant_dest_package_id,
                                                          entire_pack=entire_pack,
                                                          context=new_context)
                else:
                    # Check what you can do with reserved quants already
                    qty_on_link = move_qty_ops[move]
                    rounding = ops.product_id.uom_id.rounding
                    for reserved_quant in move.reserved_quant_ids:
                        if (reserved_quant.owner_id.id != ops.owner_id.id) or (reserved_quant.location_id.id != ops.location_id.id) or \
                                (reserved_quant.package_id.id != ops.package_id.id):
                            continue
                        if not reserved_quant.lot_id:
                            false_quants += [reserved_quant]
                        elif float_compare(lot_qty.get(reserved_quant.lot_id.id, 0), 0, precision_rounding=rounding) > 0:
                            if float_compare(lot_qty[reserved_quant.lot_id.id], reserved_quant.qty, precision_rounding=rounding) >= 0:
                                lot_qty[reserved_quant.lot_id.id] -= reserved_quant.qty
                                quants_taken += [(reserved_quant, reserved_quant.qty)]
                                qty_on_link -= reserved_quant.qty
                            else:
                                quants_taken += [(reserved_quant, lot_qty[reserved_quant.lot_id.id])]
                                lot_qty[reserved_quant.lot_id.id] = 0
                                qty_on_link -= lot_qty[reserved_quant.lot_id.id]
                    lot_move_qty[move.id] = qty_on_link
                if not move_qty.get(move.id):
                    raise UserError(_("The roundings of your Unit of Measures %s on the move vs. %s on the product don't allow to do these operations or you are not transferring the picking at once. ") % (move.product_uom.name, move.product_id.uom_id.name))
                move_qty[move.id] -= move_qty_ops[move]

            # Handle lots separately
            # if self._check_to_pack(ops):  # ops.pack_lot_ids:
            if len(ops.pack_lot_ids) > 0:
                self._move_quants_by_lot(cr, uid, ops, lot_qty, quants_taken, false_quants, lot_move_qty, quant_dest_package_id, context=context)

            # Handle pack in pack
            if not ops.product_id and ops.package_id and ops.result_package_id.id != ops.package_id.parent_id.id:
                self.pool.get('stock.quant.package').write(cr, SUPERUSER_ID, [ops.package_id.id], {'parent_id': ops.result_package_id.id}, context=context)
        # Check for remaining qtys and unreserve/check move_dest_id in
        move_dest_ids = set()
        for move in self.browse(cr, uid, ids, context=context):
            move_qty_cmp = float_compare(move_qty[move.id], 0, precision_rounding=move.product_id.uom_id.rounding)
            if move_qty_cmp > 0:  # (=In case no pack operations in picking)
                main_domain = [('qty', '>', 0)]
                preferred_domain = [('reservation_id', '=', move.id)]
                fallback_domain = [('reservation_id', '=', False)]
                fallback_domain2 = ['&', ('reservation_id', '!=', move.id), ('reservation_id', '!=', False)]
                preferred_domain_list = [preferred_domain] + [fallback_domain] + [fallback_domain2]
                self.check_tracking(cr, uid, move, False, context=context)
                qty = move_qty[move.id]
                quants = quant_obj.quants_get_preferred_domain(cr, uid, qty, move, domain=main_domain, preferred_domain_list=preferred_domain_list, context=context)
                quant_obj.quants_move(cr, uid, quants, move, move.location_dest_id, lot_id=move.restrict_lot_id.id, owner_id=move.restrict_partner_id.id, context=context)

            # If the move has a destination, add it to the list to reserve
            if move.move_dest_id and move.move_dest_id.state in ('waiting', 'confirmed'):
                move_dest_ids.add(move.move_dest_id.id)

            if move.procurement_id:
                procurement_ids.add(move.procurement_id.id)

            # unreserve the quants and make them available for other operations/moves
            quant_obj.quants_unreserve(cr, uid, move, context=context)
        # Check the packages have been placed in the correct locations
        self._check_package_from_moves(cr, uid, ids, context=context)
        # set the move as done
        self.write(cr, uid, ids, {'state': 'done', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
        self.pool.get('procurement.order').check(cr, uid, list(procurement_ids), context=context)
        # assign destination moves
        if move_dest_ids:
            self.action_assign(cr, uid, list(move_dest_ids), context=context)
        # check picking state to set the date_done is needed
        done_picking = []
        for picking in picking_obj.browse(cr, uid, list(pickings), context=context):
            if picking.state == 'done' and not picking.date_done:
                done_picking.append(picking.id)
        if done_picking:
            picking_obj.write(cr, uid, done_picking, {'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
        return True

    def _check_to_pack(self, ops):
        return len(ops.pack_lot_ids) > 0


class StockQuant(osv.osv):
    _inherit = 'stock.quant'

    def check_valuation_amount(self, cr, uid, move, valuation_amount, context=None):
        # Ignore valuation validation when picking comes from Purchase Order
        if not (move.product_id.cost_method == 'standard'):
            return False
        return move.company_id.currency_id.is_zero(valuation_amount)

    def move_quants_write(self, cr, uid, quants, move, location_dest_id, dest_package_id, lot_id=False, entire_pack=False, context=None):
        context = context or {}
        vals = {'location_id': location_dest_id.id,
                'history_ids': [(4, move.id)],
                'reservation_id': False}
        # If lot is force then use lot even when quant doesn't have lot
        if lot_id and any(x.id for x in quants if not x.lot_id.id) or context.get('force_lot_id', False):
            vals['lot_id'] = lot_id
        if not entire_pack:
            vals.update({'package_id': dest_package_id})
        self.write(cr, SUPERUSER_ID, [q.id for q in quants], vals, context=context)
        if move.product_id.valuation == 'real_time':
            self._account_entry_move(cr, uid, quants, move, context=context)

    def quants_move(self, cr, uid, quants, move, location_to, location_from=False, lot_id=False, owner_id=False, src_package_id=False, dest_package_id=False, entire_pack=False, context=None):
        """Moves all given stock.quant in the given destination location.  Unreserve from current move.
        :param quants: list of tuple(browse record(stock.quant) or None, quantity to move)
        :param move: browse record (stock.move)
        :param location_to: browse record (stock.location) depicting where the quants have to be moved
        :param location_from: optional browse record (stock.location) explaining where the quant has to be taken (may differ from the move source location in case a removal strategy applied). This parameter is only used to pass to _quant_create if a negative quant must be created
        :param lot_id: ID of the lot that must be set on the quants to move
        :param owner_id: ID of the partner that must own the quants to move
        :param src_package_id: ID of the package that contains the quants to move
        :param dest_package_id: ID of the package that must be set on the moved quant
        """
        quants_reconcile = []
        to_move_quants = []
        self._check_location(cr, uid, location_to, context=context)
        force_lot_id = context.get('force_lot_id', False)
        check_lot = False
        for quant, qty in quants:
            if not quant:
                # If quant is None, we will create a quant to move (and potentially a negative counterpart too)
                quant = self._quant_create(cr, uid, qty, move, lot_id=lot_id, owner_id=owner_id, src_package_id=src_package_id, dest_package_id=dest_package_id, force_location_from=location_from, force_location_to=location_to, context=context)
                check_lot = True
            else:
                split_quant = self._quant_split(cr, uid, quant, qty, context=context)
                if force_lot_id and split_quant:
                    to_move_quants.append(split_quant)
                else:
                    to_move_quants.append(quant)
            quants_reconcile.append(quant)
        if to_move_quants:
            to_recompute_move_ids = [x.reservation_id.id for x in to_move_quants if x.reservation_id and x.reservation_id.id != move.id]
            self.move_quants_write(cr, uid, to_move_quants, move, location_to, dest_package_id, lot_id=lot_id, entire_pack=entire_pack, context=context)
            self.pool.get('stock.move').recalculate_move_state(cr, uid, to_recompute_move_ids, context=context)
        if location_to.usage == 'internal':
            # Do manual search for quant to avoid full table scan (order by id)
            cr.execute("""
                SELECT 0 FROM stock_quant, stock_location WHERE product_id = %s AND stock_location.id = stock_quant.location_id AND
                ((stock_location.parent_left >= %s AND stock_location.parent_left < %s) OR stock_location.id = %s) AND qty < 0.0 LIMIT 1
            """, (move.product_id.id, location_to.parent_left, location_to.parent_right, location_to.id))
            if cr.fetchone():
                for quant in quants_reconcile:
                    self._quant_reconcile_negative(cr, uid, quant, move, context=context)

        # In case of serial tracking, check if the product does not exist somewhere internally already
        # Checking that a positive quant already exists in an internal location is too restrictive.
        # Indeed, if a warehouse is configured with several steps (e.g. "Pick + Pack + Ship") and
        # one step is forced (creates a quant of qty = -1.0), it is not possible afterwards to
        # correct the inventory unless the product leaves the stock.
        picking_type = move.picking_id and move.picking_id.picking_type_id or False
        if check_lot and lot_id and move.product_id.tracking == 'serial' and (not picking_type or (picking_type.use_create_lots or picking_type.use_existing_lots)):
            other_quants = self.search(cr, uid, [('product_id', '=', move.product_id.id), ('lot_id', '=', lot_id),
                                                 ('location_id.usage', '=', 'internal')], context=context)

            if other_quants:
                # We raise an error if:
                # - the total quantity is strictly larger than 1.0
                # - there are more than one negative quant, to avoid situations where the user would
                #   force the quantity at several steps of the process
                other_quants = self.browse(cr, uid, other_quants, context=context)
                if sum(other_quants.mapped('qty')) > 1.0 or len([q for q in other_quants.mapped('qty') if q < 0]) > 1:
                    lot_name = self.pool['stock.production.lot'].browse(cr, uid, lot_id, context=context).name
                    raise UserError(_('The serial number %s is already in stock.') % lot_name + _("Otherwise make sure the right stock/owner is set."))
