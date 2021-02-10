# -*- coding: utf-8 -*-
from openerp import models, fields, api, _


class account_invoice(models.Model):
    _inherit = 'account.invoice'
    
    @api.model
    def line_get_convert(self, line, part):
        res = super(account_invoice, self).line_get_convert(line, part)
        if line.get('invoice_id') and line.get('invl_id'):
                invl_rec = self.env['account.invoice.line'].browse(line['invl_id'])
                if invl_rec:
                    res['invoice_line_id'] = invl_rec.id
                    res['purchase_id'] = invl_rec.purchase_line_id and invl_rec.purchase_line_id.order_id and invl_rec.purchase_line_id.order_id.id or False
        return res
