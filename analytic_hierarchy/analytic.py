from openerp import models, fields, api

class AnalyticHierarchy(models.Model):
    _inherit = 'account.analytic.account'
    total_balance = fields.Float(string='Balance', readonly=True, compute='_balance', store=False)
    total_debit = fields.Float(string='Debit', readonly=True)
    total_credit = fields.Float(string='Credit', readonly=True)
    parent_id = fields.Many2one('account.analytic.account', string='Parent Account', 
                                domain="[('id', '!=', active_id),('internal_type' ,'=' ,'view')]")
    child_ids = fields.One2many('account.analytic.account', 'parent_id', string='Child Accounts')


    @api.one
    def _balance(self):
        if self.child_ids:
            for child in self.child_ids:
                child._balance()

        if not self.child_ids:
            self.total_balance = self.balance
            self.write({'total_debit': self.debit, 'total_credit': self.credit})
        self.total_balance = self.total_debit - self.total_credit
        if self.parent_id:
            debit = 0
            credit = 0
            for child in self.parent_id.child_ids:
                debit += child.total_debit
                credit += child.total_credit

            self.parent_id.write({'total_debit': debit, 'total_credit': credit})
