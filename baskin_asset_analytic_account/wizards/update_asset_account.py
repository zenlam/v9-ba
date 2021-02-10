# -*- coding: utf-8 -*-
from datetime import datetime
from openerp import api, fields, models, _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class UpdateAssetAccount(models.TransientModel):
    _name = 'update.asset.account'
    
    date_from = fields.Date('Date From', required=1)
    date_to = fields.Date('Date To', required=1)
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', domain=[('account_type', '=', 'normal')], required=1)
    
    @api.one
    @api.constrains('date_from', 'date_to')
    def end_date_greater_then_start(self):
        if self.date_from and self.date_to and datetime.strptime(self.date_from, DEFAULT_SERVER_DATE_FORMAT) > datetime.strptime(self.date_to,DEFAULT_SERVER_DATE_FORMAT):
            raise ValidationError(_('Start date must be smaller then end date !'))


    @api.multi
    def set_analytic_account(self):
        if self._context.get('active_id'):
            asset = self.env['account.asset.asset'].browse(self._context.get('active_id'))
            for line in asset.depreciation_line_ids:
                if line.depreciation_date >= self.date_from and line.depreciation_date <= self.date_to:
                    if line.move_check:
                        raise ValidationError(_('The dates selected includes posted depreciation entry !'))
                    else:
                        line.write({'account_analytic_id': self.account_analytic_id.id})



















