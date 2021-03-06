from openerp import models


class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'

    def do_transfer(self):
        if self.pick_id.request_id:
            self.pick_id.do_process_transfer()
        else:
            self.pick_id.do_transfer()
