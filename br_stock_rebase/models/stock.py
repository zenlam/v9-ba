from openerp.osv import osv
from openerp.tools.float_utils import float_compare
from openerp import models, fields, api, _

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    picking_orig_id = fields.Many2one(comodel_name='stock.picking', string='Destination Picking', copy=False)

class StockMove(osv.osv):
    _inherit = 'stock.move'

    def action_assign(self, cr, uid, ids, no_prepare=False, context=None):
        """ Checks the product type and accordingly writes the state.
        """
        context = context or {}
        quant_obj = self.pool.get("stock.quant")
        uom_obj = self.pool['product.uom']
        to_assign_moves = set()
        main_domain = {}
        todo_moves = []
        operations = set()
        self.do_unreserve(cr, uid, [x.id for x in self.browse(cr, uid, ids, context=context) if x.reserved_quant_ids and x.state in ['confirmed', 'waiting', 'assigned']], context=context)
        for move in self.browse(cr, uid, ids, context=context):
            if move.state not in ('confirmed', 'waiting', 'assigned'):
                continue
            if move.location_id.usage in ('supplier', 'inventory', 'production'):
                to_assign_moves.add(move.id)
                #in case the move is returned, we want to try to find quants before forcing the assignment
                if not move.origin_returned_move_id:
                    continue
            # Now allow assign quant to cunsumable product
            # if move.product_id.type == 'consu':
            #     to_assign_moves.add(move.id)
            #     continue
            # else:
            todo_moves.append(move)

            #we always search for yet unassigned quants
            main_domain[move.id] = [('reservation_id', '=', False), ('qty', '>', 0)]

            #if the move is preceeded, restrict the choice of quants in the ones moved previously in original move
            ancestors = self.find_move_ancestors(cr, uid, move, context=context)
            if move.state == 'waiting' and not ancestors:
                #if the waiting move hasn't yet any ancestor (PO/MO not confirmed yet), don't find any quant available in stock
                main_domain[move.id] += [('id', '=', False)]
            elif ancestors:
                main_domain[move.id] += [('history_ids', 'in', ancestors)]

            #if the move is returned from another, restrict the choice of quants to the ones that follow the returned move
            if move.origin_returned_move_id:
                main_domain[move.id] += [('history_ids', 'in', move.origin_returned_move_id.id)]
            for link in move.linked_move_operation_ids:
                operations.add(link.operation_id)
        # Check all ops and sort them: we want to process first the packages, then operations with lot then the rest
        operations = list(operations)
        operations.sort(key=lambda x: ((x.package_id and not x.product_id) and -4 or 0) + (x.package_id and -2 or 0) + (x.pack_lot_ids and -1 or 0))
        for ops in operations:
            #first try to find quants based on specific domains given by linked operations for the case where we want to rereserve according to existing pack operations
            if not (ops.product_id and ops.pack_lot_ids):
                for record in ops.linked_move_operation_ids:
                    move = record.move_id
                    if move.id in main_domain:
                        qty = record.qty
                        domain = main_domain[move.id]
                        if qty:
                            quants = quant_obj.quants_get_preferred_domain(cr, uid, qty, move, ops=ops, domain=domain, preferred_domain_list=[], context=context)
                            quant_obj.quants_reserve(cr, uid, quants, move, record, context=context)
            else:
                lot_qty = {}
                rounding = ops.product_id.uom_id.rounding
                for pack_lot in ops.pack_lot_ids:
                    lot_qty[pack_lot.lot_id.id] = uom_obj._compute_qty(cr, uid, ops.product_uom_id.id, pack_lot.qty, ops.product_id.uom_id.id)
                for record in ops.linked_move_operation_ids.filtered(lambda x: x.move_id.id in main_domain):
                    move_qty = record.qty
                    move = record.move_id
                    domain = main_domain[move.id]
                    for lot in lot_qty:
                        if float_compare(lot_qty[lot], 0, precision_rounding=rounding) > 0 and float_compare(move_qty, 0, precision_rounding=rounding) > 0:
                            qty = min(lot_qty[lot], move_qty)
                            quants = quant_obj.quants_get_preferred_domain(cr, uid, qty, move, ops=ops, lot_id=lot, domain=domain, preferred_domain_list=[], context=context)
                            quant_obj.quants_reserve(cr, uid, quants, move, record, context=context)
                            lot_qty[lot] -= qty
                            move_qty -= qty

        for move in todo_moves:
            #then if the move isn't totally assigned, try to find quants without any specific domain
            if (move.state != 'assigned') and not context.get("reserve_only_ops"):
                qty_already_assigned = move.reserved_availability
                qty = move.product_qty - qty_already_assigned
                quants = quant_obj.quants_get_preferred_domain(cr, uid, qty, move, domain=main_domain[move.id], preferred_domain_list=[], context=context)
                quant_obj.quants_reserve(cr, uid, quants, move, context=context)

        #force assignation of consumable products and incoming from supplier/inventory/production
        # Do not take force_assign as it would create pack operations
        if to_assign_moves:
            self.write(cr, uid, list(to_assign_moves), {'state': 'assigned'}, context=context)
        if not no_prepare:
            self.check_recompute_pack_op(cr, uid, ids, context=context)