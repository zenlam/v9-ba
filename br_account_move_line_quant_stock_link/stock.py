from openerp import fields, models, api, tools, _
from openerp.osv import fields as osv_fields
from datetime import datetime


class stock_quant(models.Model):
    _inherit = 'stock.quant'

    def _prepare_account_move_line(self, cr, uid, move, qty, cost, credit_account_id, debit_account_id, context=None):
        res = super(stock_quant, self)._prepare_account_move_line(cr, uid, move, qty, cost, credit_account_id,
                                                                  debit_account_id, context=context)
        quant_ids = context.get('quant_ids', False)
        if quant_ids:
            if res and res[0] and res[0][2]:
                res[0][2].update({
                    'quant_ids': [(6, 0, quant_ids)],
                    'stock_move_id': move.id,
                    'purchase_id': move.purchase_line_id and move.purchase_line_id.order_id and move.purchase_line_id.order_id.id or False 
                })
            if res and res[1] and res[1][2]:
                res[1][2].update({
                    'quant_ids': [(6, 0, quant_ids)],
                    'stock_move_id': move.id,
                    'purchase_id': move.purchase_line_id and move.purchase_line_id.order_id and move.purchase_line_id.order_id.id or False
                })
        return res
#
#
# class br_stock_move(models.Model):
#     _inherit = 'stock.move'
#
#     inventory_line_id = fields.Many2one(comodel_name='stock.inventory.line')
#
#
# class br_stock_inventory_line(models.Model):
#     _inherit = 'stock.inventory.line'
#
#     def get_stock_move_vals(self, cr, uid, inventory_line, context=None):
#         """
#         Add inventory_line_id to stock move
#         """
#         res = super(br_stock_inventory_line, self).get_stock_move_vals(cr, uid, inventory_line, context=context)
#         res.update(inventory_line_id=inventory_line.id)
#         return res
