from openerp import models, api


class BRAccountMove(models.Model):
    _inherit = "account.move"

    @api.multi
    def button_cancel(self):
        flag = True
        for move in self:
            if not move.journal_id.update_posted:
                flag = False
        if flag:
            if self.ids:
                self._check_lock_date()
        res = super(BRAccountMove, self).button_cancel()
        return res

BRAccountMove()
