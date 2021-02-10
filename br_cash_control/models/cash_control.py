# --*-- coding: utf-8 --*--
from openerp import models, api, fields, _


class cash_control(models.Model):
    _name = 'br.cash.control'
    _order = 'action, name ASC'

    name = fields.Char(string=_('Name'), help=_("Reason Name"), required=True)
    action = fields.Selection(string=_('Action'), selection=[
        ('put_in','Put In'),
        ('failed_bank_in', 'Failed Bank In'),
        ('take_out', 'Take Out'),
        ('bank_in', 'Bank In'),
    ], required=True)

    def _default_company_id(self):
        company_model = self.env['res.company']
        return company_model._company_default_get(self._name)

    @api.multi
    def toggle_is_active(self):
        """ Inverse the value of the field ``active`` on the records in ``self``. """
        for record in self:
            record.is_active = not record.is_active


    company_id = fields.Many2one(comodel_name='res.company', string=_("Company"), default=_default_company_id, required=True)
    debit_account_id = fields.Many2one(comodel_name='account.account', string=_("Debit Account"), required=True)
    credit_account_id = fields.Many2one(comodel_name='account.account', string=_("Credit Account"), required=True)
    is_active = fields.Boolean(string="Active", default=True)


class account_bank_statement_line(models.Model):
    _inherit = 'account.bank.statement.line'

    cash_control_id = fields.Many2one(comodel_name='br.cash.control')
