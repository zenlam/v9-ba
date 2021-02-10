# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    active_in_journal_entry = fields.Boolean('Active in Manual Journal')
    type = fields.Selection(selection_add=[('opening', 'Opening')])

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    is_import = fields.Boolean('Is Imported?', default=False)

    @api.multi
    @api.onchange('is_import')
    def onchange_is_import(self):
        if self.is_import:
            return{
                'domain': {
                    'journal_id': [('type', 'in',
                                    {'out_invoice': ['sale', 'opening'], 'out_refund': ['sale', 'opening'],
                                     'in_refund': ['purchase', 'opening'], 'in_invoice': ['purchase', 'opening']}.get(
                                        self.type, [])),
                                   ('company_id', '=', self.company_id.id)],
                }
            }
        else:
            return{
                'domain': {
                    'journal_id': [('type', 'in',
                                    {'out_invoice': ['sale'], 'out_refund': ['sale'],
                                     'in_refund': ['purchase'],
                                     'in_invoice': ['purchase']}.get(self.type, [])),
                                   ('company_id', '=', self.company_id.id)],
                }
            }



class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.multi
    def _get_default_journal(self):
        if self.env.context.get('default_journal_type'):
            return self.env['account.journal'].search([
                ('type', '=', self.env.context['default_journal_type']),
                ('active_in_journal_entry', '=', True)
            ], limit=1)

    journal_id = fields.Many2one(default=_get_default_journal)
    memo = fields.Char('Memo', size=30)


class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    @api.multi
    def _get_label_name(self):
        name = ''
        if self.env.context.get('memo'):
            name = self.env.context['memo']
        return name

    name = fields.Char(default=_get_label_name)


class AccountMoveCancel(models.TransientModel):
    """
    This wizard will cancel all the selected journal entries.
    """

    _name = "account.move.cancel"
    _description = "Cancel the Selected Journal Entries"

    @api.multi
    def move_cancel(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        for record in self.env['account.move'].browse(active_ids):
            if record.state == 'posted':
                record.button_cancel()
            else:
                raise UserError(_("Selected entries cannot be cancelled as they are not in 'Posted' state."))
        return {'type': 'ir.actions.act_window_close'}
