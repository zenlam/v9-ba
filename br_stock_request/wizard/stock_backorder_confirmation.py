from openerp import models, api, fields, _


class StockBackOrderConfirmation(models.TransientModel):
    _inherit = 'stock.backorder.confirmation'

    def do_transfer(self):
        if self.pick_id.request_id:
            self.pick_id.do_process_transfer()
        else:
            self.pick_id.do_transfer()
