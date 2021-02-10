# -*- coding: utf-8 -*-

from openerp import api, fields, models


class Account(models.Model):
    _inherit = 'account.account'

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    internal_type = fields.Selection(related='user_type_id.type', store=True, readonly=True, string="Account Type's Type")

    @api.model
    def create(self, vals):
        """ hotfix: Solve the issue of unable to create account account from
        bank accounts menuitem """
        # if 'type' is not found in the values dictionary, then we need to pass
        # type as 'other' as default value
        if 'type' not in vals:
            vals.update({'type': 'other'})
        return super(Account, self).create(vals)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    payment_move_line_id = fields.Many2one('account.move.line', string='Payment Move Line')
    cheque_no = fields.Char('Cheque No')
    # debit = fields.Float(digits=dp.get_precision('Product Price'))
    # credit = fields.Float(digits=dp.get_precision('Product Price'))
    # balance = fields.Float(digits=dp.get_precision('Product Price'))
    # debit_cash_basis = fields.Monetary(digits=dp.get_precision('Product Price'))
    # credit_cash_basis = fields.Monetary(digits=dp.get_precision('Product Price'))
    # balance_cash_basis = fields.Monetary(digits=dp.get_precision('Product Price'))

    @api.one
    def _prepare_analytic_line(self):
        vals = super(AccountMoveLine, self)._prepare_analytic_line()
        vals[0]['internal_remarks'] = self.move_id and self.move_id.internal_remarks or ''
        vals[0]['imported_on'] = self.move_id and self.move_id.imported_on or False
        return vals[0]

    @api.multi
    def remove_move_reconcile(self):
        res = super(AccountMoveLine, self).remove_move_reconcile()
        for line in self:
            # move_lines = self.search([('payment_move_line_id', '=', line.payment_move_line_id.id)])
            if line.payment_move_line_id:
                rec_move_ids = self.env['account.partial.reconcile']
                query = """SELECT id FROM account_move_line where payment_move_line_id = %s"""
                self.env.cr.execute(query, (line.payment_move_line_id.id,))
                line_ids = [x[0] for x in self.env.cr.fetchall()]
                if line_ids:
                    move_lines = self.browse(line_ids)
                    for line in move_lines:
                        rec_move_ids += line.matched_debit_ids
                        rec_move_ids += line.matched_credit_ids
                    rec_move_ids.unlink()
                    move_lines.write({'payment_move_line_id': False})
        return res


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    code = fields.Char(size=10)


class AccountMove(models.Model):
    _inherit = 'account.move'

    internal_remarks = fields.Text('Internal Remarks')
    imported_on = fields.Date('Imported On')


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    internal_remarks = fields.Text('Internal Remarks')
    imported_on = fields.Date('Imported On')
