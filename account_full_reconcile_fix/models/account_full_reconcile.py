# -*- coding: utf-8 -*-

from openerp import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class account_move_line(models.Model):
    _inherit = 'account.move.line'

    @api.multi
    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        """ Call the _amount_residual to recalculate the amount_residual to handle the issue of wrong configuration (allow reconciliation in account) """
        for rec in self:
            rec._amount_residual()
        return super(account_move_line, self).reconcile(writeoff_acc_id=writeoff_acc_id, writeoff_journal_id=writeoff_journal_id)

    @api.multi
    def remove_move_reconcile(self):
        """ Remove the full reconcile id """
        rec_full_move_ids = self.env['account.full.reconcile']
        for aml in self:
            rec_full_move_ids += aml.full_reconcile_id
        if rec_full_move_ids:
            rec_full_move_ids.unlink()
        return super(account_move_line, self).remove_move_reconcile()
