# -*- coding: utf-8 -*-

from openerp import fields, models, api, _
from openerp.exceptions import UserError


class AnalyticGroup(models.Model):
    _name = 'analytic.group'
    _order = 'sequence asc'

    name = fields.Char('Group Name', required=True)
    enable_pl_grouping = fields.Boolean('Enable P&L Grouping')
    analytic_account_ids = fields.Many2many('account.analytic.account', string='Analytic Accounts',
                                             domain=[('account_type', '=', 'normal')])
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get('analytic.group'))
    sequence = fields.Integer(string="Sequence",default=1)
    
    @api.one
    @api.constrains('analytic_account_ids')
    def _check_account_analytic_method_unique(self):
        # Constraint should be one account can not be associate with two group
        if self.analytic_account_ids:
            account_names = []
            for config in self.search([('id','!=',self.id)]):
                for account in self.analytic_account_ids:
                    if account.id in [x.id for x in config.analytic_account_ids]:
                        account_names.append(account.name)
            if account_names:
                raise UserError(_('You can not configure "%s" for two different Group !'% ', '.join(account_names)))