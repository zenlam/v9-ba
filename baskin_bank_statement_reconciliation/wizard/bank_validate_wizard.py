# -*- coding: utf-8 -*-

from openerp import models, fields, api
import logging
_logger = logging.getLogger(__name__) 

class bank_validate_wizard(models.TransientModel):
    _name = 'bank.validate.wizard'
    
    future_record_ref = fields.Text('Future records numbers')
    
    @api.model
    def default_get(self, fields):
        context = self._context or {}
        res = super(bank_validate_wizard, self).default_get(fields)
        future_record_ref = ''
        if self._context.get('active_id'):
            bank_recon = self.env['bank.statement.reconcile'].browse(self._context.get('active_id'))
            future_records = bank_recon.get_future_statement()
            future_record_ref = ', \n'.join([x.name for x in future_records])
        res.update({
            'future_record_ref': future_record_ref,
        })
        return res
    
    @api.multi
    def apply(self):
        self.ensure_one()
        if self._context.get('active_id'):
            bank_recon = self.env['bank.statement.reconcile'].browse(self._context.get('active_id'))
            bank_recon.validate()
        return True
    
    