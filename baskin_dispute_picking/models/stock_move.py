from openerp import models, fields, api


class DisputeStockMove(models.Model):
    _inherit = 'stock.move'

    initial_move_qty = fields.Float(string="Initial Move Qty")
    is_dispute_move = fields.Boolean(string="Dispute Move", default=False, store=True)
    is_accept_dispute = fields.Boolean(string='Accept Dispute', default=False, store=True)
    is_reject_dispute = fields.Boolean(string='Reject Dispute', default=False, store=True)
    is_disagree_dispute = fields.Boolean(string='Disagree Dispute', default=False, store=True)
    adjusted_dispute_qty = fields.Float(string='Adjusted Dispute Qty', default=0, store=True)
    request_id = fields.Many2one(comodel_name='br.stock.request.transfer', string="Transfer", store=True)