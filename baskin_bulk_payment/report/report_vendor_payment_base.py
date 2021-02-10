# -*- coding: utf-8 -*-

import time
from openerp import api, models, _
from openerp.exceptions import UserError


class ReportBaskinVendorPaymentBase(models.AbstractModel):
    _name = 'report.baskin_bulk_payment.report_baskin_vendor_payment_base'

    def get_posting_date(self, doc):
        AccountInvoice = self.env['account.invoice']
        posting_date = False
        invoice = AccountInvoice.search([('move_id', '=', doc.move_line_id.move_id.id)])
        posting_date = invoice.date_invoice
        return posting_date

    @api.multi
    def render_html(self, data):
        docs = self.env['account.payment'].browse(self.ids)
        if any(not line.is_same_currency for line in docs):
            raise UserError(_('You can print this report only for Payment same with Inv Currency)'))
        docargs = {
            'get_posting_date': self.get_posting_date,
            'doc_ids': self.ids,
            'doc_model': 'account.payment',
            'docs': docs,
            'time': time,
        }
        return self.env['report'].render('baskin_bulk_payment.report_baskin_vendor_payment_base', docargs)
