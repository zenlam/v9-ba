from openerp import api, models, fields, _
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'
    
    reason_of_reverse = fields.Many2one('reverse.transfer.reason.category', string="Reason of Reverse")
    remarks = fields.Text("Remarks")
    reason_require = fields.Boolean('Reason Required')
    picking_code = fields.Selection([('incoming', 'Suppliers'), ('outgoing', 'Customers'), ('internal', 'Internal')], 'Picking code')
    need_remarks = fields.Boolean('Need Remarks')
    
    @api.model
    def default_get(self, fields):
        rec = super(StockReturnPicking, self).default_get(fields)
        record_id = self._context and self._context.get('active_id', False) or False
        pick_obj = self.env['stock.picking']
        pick = pick_obj.browse(record_id)
        if pick.picking_type_id.need_reverse_transfer_reason:
            rec['reason_require'] = True
        if pick.picking_type_id.code:
            rec['picking_code'] = pick.picking_type_id.code
        return rec
    
    @api.onchange('reason_of_reverse')
    def onchange_reason_of_reverse(self):
        if self.reason_of_reverse and self.reason_of_reverse.need_remarks:
            self.need_remarks = True
        else:
            self.need_remarks = False
    
    @api.model
    def _get_move_values(self, move, data_get, new_qty, new_picking, location_id, pick_type_id, pick, move_dest_id, data):
        """to add two more values for move"""
        res = super(StockReturnPicking, self)._get_move_values(move, data_get, new_qty, new_picking, location_id, pick_type_id, pick, move_dest_id, data)
        res.update({'reason_of_reverse': data['reason_of_reverse'] and data['reason_of_reverse'][0] or False,
                    'remarks': data['remarks'] or ''})
        return res
    
    @api.model
    def _get_picking_values(self, pick_type_id, pick, data):
        """Get Reverse Move Value"""
        res = super(StockReturnPicking, self)._get_picking_values(pick_type_id, pick, data)
        res.update({'reason_of_reverse': data['reason_of_reverse'] and data['reason_of_reverse'][0] or False,
                    'remarks': data['remarks'] or ''})
        return res
            
