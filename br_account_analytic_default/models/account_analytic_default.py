# -*- coding: utf-8 -*-
from openerp import models, fields, api


class BRAccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _set_additional_fields(self, invoice):
        if not self.account_analytic_id:
            rec = self.env['account.analytic.default'].account_get(self.product_id.id, self.invoice_id.partner_id.id,
                                                                   self._uid,
                                                                   time.strftime('%Y-%m-%d'),
                                                                   company_id=self.company_id.id, context=self._context)
            if rec:
                self.account_analytic_id = rec.analytic_id.id
        super(BRAccountMoveLine, self)._set_additional_fields(invoice)

BRAccountMoveLine()
