# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = "ir.attachment"
    
    invoice_id = fields.Many2one('account.invoice', string="Invoice")
    
    @api.model
    def create(self, vals):
        if vals.get('res_id') and vals.get('res_model') and vals.get('res_model') == 'account.invoice':
            vals['invoice_id'] = vals.get('res_id') 
        return super(IrAttachment, self).create(vals)
    
    @api.multi
    def write(self, vals):
        if vals.get('res_id') and not vals.get('res_model'):
            for attachment in self:
                if attachment.res_model == 'account.invoice':
                    vals['invoice_id'] = vals.get('res_id')
        elif vals.get('res_model') and not vals.get('res_id'):
            for attachment in self:
                if attachment.res_model == 'account.invoice' and vals.get('res_model') != 'account.invoice':                    
                    vals['invoice_id'] = False
        elif vals.get('res_model') and vals.get('res_id'):
            for attachment in self:
                if attachment.res_model == 'account.invoice' and vals.get('res_model') != 'account.invoice':
                    vals['invoice_id'] = False
                elif attachment.res_model == 'account.invoice' and vals.get('res_model') == 'account.invoice':
                    vals['invoice_id'] = vals.get('res_id')
                    
        return super(IrAttachment, self).write(vals)
    