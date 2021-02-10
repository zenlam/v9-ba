# -*- coding: utf-8 -*-
__author__ = 'truongnn'
from openerp import models, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Remove fields when updating the same old value
    @api.multi
    def write(self, vals):
        # TruongNN
        if ('account_id' in vals) and vals['account_id'] and vals['account_id'] == self.account_id.id:
            del (vals['account_id'])
        # TruongNN
        return super(AccountMoveLine, self).write(vals)
