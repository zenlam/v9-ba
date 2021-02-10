# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class AccountInvoice(models.Model):
    _inherit = "account.invoice"
    
    @api.depends('attachment_ids')
    @api.one
    def _compute_attachment_count(self):
        if self.attachment_ids:
            _logger.info("-------count %s %s"%(self.attachment_ids, len(self.attachment_ids)))
            self.attachment_count = len(self.attachment_ids)
    
    invoice_id_ref = fields.Many2one('account.invoice', 'Invoice Ref', copy=False, readonly=True)
    invoice_refund_refs = fields.One2many('account.invoice', 'invoice_id_ref', string="Refunded Invoice", readonly=True)
    cn_required = fields.Selection([('yes','Yes'),('no','No')], "CN Required")
    cn_done = fields.Selection([('yes','Yes'),('no','No')], "CN Done")
    attachment_ids = fields.One2many('ir.attachment', 'invoice_id', string='Attachments')
    attachment_count = fields.Integer(compute="_compute_attachment_count", store=True, string="Attachment")
    
    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        res = super(AccountInvoice, self)._prepare_refund(invoice, date_invoice=date_invoice, date=date, description=description, journal_id=journal_id)
        res['invoice_id_ref'] = invoice.id
        return res
    
    @api.multi
    def invoice_validate(self):
        res = super(AccountInvoice, self).invoice_validate()
        for invoice in self:
            if invoice.type in ['out_refund','in_refund'] and invoice.invoice_id_ref:
                if invoice.invoice_id_ref.state == 'open':
                    domain = [('move_id.id','=',invoice.invoice_id_ref.move_id.id),
                              ('account_id', '=', self.account_id.id), 
                              ('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id), 
                              ('reconciled', '=', False), 
                              ('amount_residual', '!=', 0.0)]
                    if self.type in ('out_invoice', 'in_refund'):
                        domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                    else:
                        domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                    
                    lines = self.env['account.move.line'].search(domain)
                    
                    for line in lines:
                        # NOTE : This method "assign_outstanding_credit" is for add/reconcile refund invoice amount with origin invoice
                        self.pool['account.invoice'].assign_outstanding_credit(self._cr, self._uid, invoice.id, line.id, context=self._context)
        return res 

    @api.multi
    def action_bulk_refund_invoice(self):
        context = dict(self.env.context or {})
        
        partner_ids = []
        invoice_ids = []
        not_open = False
        not_refund_type = False
        for invoice in self:
            invoice_ids.append(invoice.id)
            if partner_ids and invoice.partner_id.id not in partner_ids:
                raise UserError("You must select all invoice from same customer/vendor.")
            partner_ids.append(invoice.partner_id.id)
            
            if invoice.state != 'open':
                not_open = True
                
            if invoice.type not in ['out_invoice', 'in_invoice']:
                not_refund_type = True
                
        if not_refund_type:
            raise UserError("Please select Invoice, To create bulk refund.")
        if not_open:
            raise UserError(_('Cannot refund draft/proforma/paid/cancelled invoice.'))
            
        context['invoice_ids'] = invoice_ids
        return {
                'name': _('Bulk Refund Invoice'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'invoice.matching',
                'view_id': self.env.ref('baskin_credit_note.view_invoice_matching').id,
                'type': 'ir.actions.act_window',
                'context': context,
                'target': 'new'
            }
            
