# -*- coding: utf-8 -*-

from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from openerp.exceptions import ValidationError, UserError
from openerp.tools.translate import _
import logging
_logger = logging.getLogger(__name__) 

class account_move_line(models.Model):
    _inherit = "account.move.line"

    bank_state = fields.Selection([('draft','Open'),('match','Matched')], default="draft", string="Bank Status", readonly=True, copy=False)
    bank_statement_id = fields.Many2one('bank.statement.reconcile', string='Bank Statement Reconcile', copy=False)
    
    @api.multi
    def unlink(self):
        msg = "This entries already matched with %s Bank Reconciliation statement, you cannot Delete! \n To Delete this entries, You have to make set to draft %s bank Reconciliation entry."
        for acc_mv_line in self:
            if acc_mv_line.bank_state == 'match':
                raise ValidationError(_(msg%(acc_mv_line.bank_statement_id.name,acc_mv_line.bank_statement_id.name)))
        return super(account_move_line, self).unlink()
    
#     @api.multi
#     def validate_bank_recon_statement(self):
#         msg = "This entries already matched with %s Bank Reconciliation statement, you cannot do Un-reconcile or edit! \n To Un-reconcile or edit this entries, You have to make set to draft %s bank Reconciliation entry."
#         bank_statment_ref = []
#         for move_line in self:
#             if move_line.bank_state == 'match':
#                 bank_statment_ref.append(move_line.bank_statement_id.name)
#                 #raise ValidationError(_('This entries are locked inside bank reconciliation cannot be Un-reconcile !'))
#             for aml in move_line.move_id.line_ids:
#                 #if aml.account_id.reconcile:
#                     #ids.extend([r.debit_move_id.id for r in aml.matched_debit_ids] if aml.credit > 0 else [r.credit_move_id.id for r in aml.matched_credit_ids])
#                     if aml.credit > 0 :
#                         for r in aml.matched_debit_ids:
#                             if r.debit_move_id.bank_state == 'match':
#                                 bank_statment_ref.append(aml.bank_statement_id.name)
#                                 #raise ValidationError(_('This entries are locked inside bank reconciliation cannot be Un-reconcile !'))
#                     else:
#                         for r in aml.matched_credit_ids:
#                             if r.credit_move_id.bank_state == 'match':
#                                 bank_statment_ref.append(aml.bank_statement_id.name)
#                                 #raise ValidationError(_('This entries are locked inside bank reconciliation cannot be Un-reconcile !'))
#                     
#                     if aml.bank_state == 'match':
#                         bank_statment_ref.append(aml.bank_statement_id.name)
#                         #raise ValidationError(_('This entries are locked inside bank reconciliation cannot be Un-reconcile !'))
#         if bank_statment_ref:
#             ref_string = ', '.join([str(x) for x in bank_statment_ref])
#             raise ValidationError(msg%(ref_string,ref_string))
#             
#     @api.multi
#     def remove_move_reconcile(self):
#         """ Undo a reconciliation """
#         if not self:
#             return True
#         self.validate_bank_recon_statement()
#         return super(account_move_line, self).remove_move_reconcile()
#     
#     @api.multi
#     def write(self, vals):
#         self.validate_bank_recon_statement()
#         return super(account_move_line, self).write(vals)
    
class account_move(models.Model):
    _inherit = "account.move"

    @api.multi
    def button_cancel(self):
        msg = "This entries already matched with %s Bank Reconciliation statement, you cannot Cancel! \n To Cancel this entries, You have to make set to draft %s bank Reconciliation entry."
        for move in self:
            for line in move.line_ids:
                if line.bank_state == 'match':
                    raise ValidationError(_(msg%(line.bank_statement_id.name,line.bank_statement_id.name)))
        
        return super(account_move, self).button_cancel()