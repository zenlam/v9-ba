from openerp import fields, models, api, _


class StockBackOrderConfimration(models.TransientModel):
    _inherit = 'stock.backorder.confirmation'

    @api.multi
    def _process(self, cancel_backorder=False):
        self.ensure_one()
        operations_to_delete = self.pick_id.pack_operation_ids.filtered(lambda o: o.qty_done <= 0)
        for pack in self.pick_id.pack_operation_ids - operations_to_delete:
            pack.product_qty = pack.qty_done
        if operations_to_delete:
            operations_to_delete.unlink()
        self.do_transfer()
        if cancel_backorder:
            backorder_pick = self.env['stock.picking'].search([('backorder_id', '=', self.pick_id.id)])
            backorder_pick.action_cancel()
            self.pick_id.message_post(body=_("Back order <em>%s</em> <b>cancelled</b>.") % (backorder_pick.name))

    def do_transfer(self):
        """Do Picking Transfer"""
        self.pick_id.do_transfer()