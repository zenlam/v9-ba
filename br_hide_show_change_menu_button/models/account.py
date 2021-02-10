# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError


TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Vendor Bill
    'out_refund': 'out_invoice',        # Customer Refund
    'in_refund': 'in_invoice',          # Vendor Refund
}


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.constrains('reference')
    def _check_reference(self):
        if self.reference and self.type in ('in_invoice', 'in_refund'):
            ref = self.reference.replace(' ', '')
            query = """SELECT id FROM account_invoice where partner_id = %s and trim(replace(reference, ' ', '')) = %s and id != %s"""
            self.env.cr.execute(query, (self.partner_id.id, ref, self.id))
            res = self.env.cr.fetchall()
            if len(res) >= 1:
                raise UserError(_('The Doc No/Ref of the Vendor must be unique per Vendor !'))

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        values = super(AccountInvoice, self)._prepare_refund(invoice, date_invoice=date_invoice, date=date, description=description, journal_id=journal_id)
        if invoice['type'] == 'in_invoice' and values.get('reference'):
            values['reference'] = False
        return values

    # @api.model
    # def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
    #     res = super(AccountInvoice, self).fields_view_get(
    #         view_id=view_id,
    #         view_type=view_type,
    #         toolbar=toolbar,
    #         submenu=submenu)
    #     if res.get('name') == 'account.invoice.supplier.form' or res.get('name') == 'account.invoice.supplier.tree':
    #         if res.get('toolbar', False) and res.get('toolbar').get('print', False):
    #             del res['toolbar']['print']
    #     return res
