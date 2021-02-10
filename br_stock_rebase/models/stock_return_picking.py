from openerp.osv import osv
from openerp.tools.translate import _
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StockReturnPkcing(osv.osv_memory):
    _inherit = 'stock.return.picking'

    def _create_returns(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        record_id = context and context.get('active_id', False) or False
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        uom_obj = self.pool.get('product.uom')
        data_obj = self.pool.get('stock.return.picking.line')
        pick = pick_obj.browse(cr, uid, record_id, context=context)
        data = self.read(cr, uid, ids[0], context=context)
        returned_lines = 0

        # Cancel assignment of existing chained assigned moves
        moves_to_unreserve = []
        for move in pick.move_lines:
            to_check_moves = [move.move_dest_id] if move.move_dest_id.id else []
            while to_check_moves:
                current_move = to_check_moves.pop()
                if current_move.state not in ('done', 'cancel') and current_move.reserved_quant_ids:
                    moves_to_unreserve.append(current_move.id)
                split_move_ids = move_obj.search(cr, uid, [('split_from', '=', current_move.id)], context=context)
                if split_move_ids:
                    to_check_moves += move_obj.browse(cr, uid, split_move_ids, context=context)

        if moves_to_unreserve:
            move_obj.do_unreserve(cr, uid, moves_to_unreserve, context=context)
            # break the link between moves in order to be able to fix them later if needed
            move_obj.write(cr, uid, moves_to_unreserve, {'move_orig_ids': False}, context=context)

        # Create new picking for returned products
        pick_type_id = context.get('picking_type_id', False) or pick.picking_type_id.return_picking_type_id and pick.picking_type_id.return_picking_type_id.id or pick.picking_type_id.id
        new_picking = pick_obj.copy(cr, uid, pick.id, self._get_picking_values(cr, uid, pick_type_id, pick, data, context=context), context=context)

        for data_get in data_obj.browse(cr, uid, data['product_return_moves'], context=context):
            move = data_get.move_id
            if not move:
                raise UserError(_("You have manually created product lines, please delete them to proceed"))
            new_qty = data_get.quantity
            if new_qty:
                # The return of a return should be linked with the original's destination move if it was not cancelled
                if move.origin_returned_move_id.move_dest_id.id and move.origin_returned_move_id.move_dest_id.state != 'cancel':
                    move_dest_id = move.origin_returned_move_id.move_dest_id.id
                else:
                    move_dest_id = False

                returned_lines += 1
                location_id = data['location_id'] and data['location_id'][0] or move.location_id.id
                move_obj.copy(cr, uid, move.id, self._get_move_values(cr, uid, move, data_get, new_qty, new_picking, location_id, pick_type_id, pick, move_dest_id, data, context=context))

        if not returned_lines:
            raise UserError(_("Please specify at least one non-zero quantity."))
        if not context.get('skip_assign_picking', False):
            pick_obj.action_confirm(cr, uid, [new_picking], context=context)
            pick_obj.action_assign(cr, uid, [new_picking], context=context)
        return new_picking, pick_type_id

    def _get_move_values(self, cr, uid, move, data_get, new_qty, new_picking, location_id, pick_type_id, pick, move_dest_id, data, context=None):
        """Get Reverse Move Value"""
        picking_type = self.pool.get('stock.picking.type').browse(cr, uid, pick_type_id, context=context)
        return {
            'product_id': data_get.product_id.id,
            'product_uom_qty': new_qty,
            'picking_id': new_picking,
            'state': 'draft',
            'location_id': move.location_dest_id.id,
            'location_dest_id': location_id,
            'picking_type_id': pick_type_id,
            'warehouse_id': pick.picking_type_id.warehouse_id.id,
            'origin_returned_move_id': move.id,
            'procure_method': 'make_to_stock',
            'move_dest_id': move_dest_id,
            'is_dispute_move': True if picking_type.is_dispute is True else False,
            'request_id': move.request_line_id.transfer_id.id,
            'initial_move_qty': new_qty
        }
        
    def _get_picking_values(self, cr, uid, pick_type_id, pick, data, context=None):
        """Get Reverse Move Value"""
        return {
            'move_lines': [],
            'picking_type_id': pick_type_id,
            'state': 'draft',
            'origin': pick.name,
            'location_id': pick.location_dest_id.id,
            'location_dest_id': data['location_id'] and data['location_id'][0] or pick.location_id.id,
            'picking_orig_id': pick.id
        }
