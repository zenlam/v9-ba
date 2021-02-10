# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import ValidationError


class ReScurrency(models.Model):
    _inherit = 'res.currency'

    def _get_current_direct_rate(self):
        date = self.env.context.get('date') or fields.Datetime.now()
        company_id = self.env.context.get('company_id') or self.env.user.company_id.id
        for rec in self:
            self.env.cr.execute("""SELECT direct_rate FROM res_currency_rate
                           WHERE currency_id = %s
                             AND name <= %s
                             AND (company_id is null
                                 OR company_id = %s)
                        ORDER BY company_id, name desc LIMIT 1""",
                                (rec.id, date, company_id))
            if self.env.cr.rowcount:
                rec.direct_rate = self.env.cr.fetchone()[0]
            else:
                rec.direct_rate = 1

    direct_rate = fields.Float(compute='_get_current_direct_rate', string='Direct Current Rate', digits=(12, 12))


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    direct_rate = fields.Float('Indirect Rate', digits=(12, 12))
    backend_rate = fields.Float('Direct Rate', digits=(12, 12))

    @api.constrains('direct_rate')
    def _check_direct_rate(self):
        print "hello"
        for rate in self:
            if rate.direct_rate <= 0.0:
                raise ValidationError((_('Indirect Rate value must be more than zero!.')))

    @api.onchange('direct_rate')
    def onchange_direct_rate(self):
        if self.direct_rate != 0:
            self.rate = 1 / self.direct_rate
            self.backend_rate = 1 / self.direct_rate

    @api.model
    def create(self, vals):
        if vals.get('backend_rate'):
            vals['rate'] = vals['backend_rate']
        return super(ResCurrencyRate, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('backend_rate'):
            vals['rate'] = vals['backend_rate']
        return super(ResCurrencyRate, self).write(vals)
