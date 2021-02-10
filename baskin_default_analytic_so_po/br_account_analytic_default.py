# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from openerp import fields, api, models, _
from openerp import api


class account_invoice_line(models.Model):
    _inherit = "account.invoice.line"

    @api.onchange('product_id')
    def _onchange_product_id(self):
        res = super(account_invoice_line, self)._onchange_product_id()
        rec = self.env['account.analytic.default'].account_get(self.product_id.id, self.invoice_id.partner_id.id, self._uid,
                                                               time.strftime('%Y-%m-%d'), company_id=self.env.user.company_id.id, context=self._context)
        if rec:
            self.account_analytic_id = rec.analytic_id.id
        else:
            analytic_account = self.env['account.analytic.account'].search([('partner_id', '=', self.invoice_id.partner_id.id)], limit=1)
            if analytic_account:
                self.account_analytic_id = analytic_account.id
        return res
    
class sale_account(models.Model):
    _inherit = 'sale.order'

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        super(sale_account, self).onchange_partner_id()
        if self.partner_id:
            rec = self.env['account.analytic.default'].account_get(False, self.partner_id.id,
                                                                   self._uid,
                                                                   time.strftime('%Y-%m-%d'),
                                                                   company_id=self.env.user.company_id.id, context=self._context)
            if rec:
                self.update({
                    'project_id': rec.analytic_id.id
                })
            else:
                analytic_account = self.env['account.analytic.account'].search([('partner_id', '=', self.partner_id.id)], limit=1)
                if analytic_account:
                    self.update({
                        'project_id': analytic_account.id
                    })
                    
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('product_id')
    def onchange_product_id(self):
        res = super(PurchaseOrderLine, self).onchange_product_id()
        rec = self.env['account.analytic.default'].account_get(self.product_id.id, self.order_id.partner_id.id, self._uid,
                                                               time.strftime('%Y-%m-%d'), company_id=self.env.user.company_id.id, context=self._context)
        if rec:
            self.account_analytic_id = rec.analytic_id.id
        else:
            analytic_account = self.env['account.analytic.account'].search([('partner_id', '=', self.order_id.partner_id.id)], limit=1)
            if analytic_account:
                self.account_analytic_id = analytic_account.id
        return res