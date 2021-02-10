from openerp import api, models, fields, _


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    need_reverse_transfer_reason = fields.Boolean(string=_("Need Reverse Transfer Reason"), default=False)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    reason_of_reverse = fields.Many2one('reverse.transfer.reason.category', string="Reason of Reverse")
    remarks = fields.Text("Remarks")
    
class StockMove(models.Model):
    _inherit = 'stock.move'

    reason_of_reverse = fields.Many2one('reverse.transfer.reason.category', string="Reason of Reverse")
    remarks = fields.Text("Remarks")

