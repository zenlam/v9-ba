# -*- coding: utf-8 -*-

from openerp import api, models


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        if self._context.get('forex_currency'):
            company_currency = self.env.user.company_id.currency_id
            domain += [('id', '!=', company_currency.id)]
        return super(ResCurrency, self).name_search(
            name, args=domain+args, operator=operator, limit=limit)
