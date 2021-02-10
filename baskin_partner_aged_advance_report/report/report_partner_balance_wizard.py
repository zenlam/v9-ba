# -*- coding: utf-8 -*-

import time
from datetime import datetime
from openerp import api, fields, models, _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError, ValidationError


class PartnerStatementReport(models.TransientModel):
    _name = 'partner.statement.wizard'
    
    
    report_type = fields.Selection([('all', 'All Transaction'),
                                    ('outstanding', 'Outstanding'),
                                    ], string='Report Type', required=True, default='all')
    result_selection = fields.Selection([('customer', 'Receivable Accounts'),
                                        ('supplier', 'Payable Accounts'),
                                        ('customer_supplier', 'Receivable and Payable Accounts')
                                      ], string="Partner's", required=True, default='customer')
    partner_ids = fields.Many2many('res.partner','state_rel_partner','partner_id','parent_id','Partner', required=True)
    date_from = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    currency_selection = fields.Selection([('base_currency','Base Currency'),
                                           ('foreign_currency','Foreign Currency')],
                                           'Currency', default='base_currency', required=True)
    target_move = fields.Selection([('posted', 'All Posted Entries'),
                                    ('all', 'All Entries'),
                                    ], string='Target Moves', required=True, default='all')
    
    @api.one
    @api.constrains('date_from', 'date_end')
    def end_date_greater_then_start(self):
        if self.date_from and self.date_end and datetime.strptime(self.date_from,DEFAULT_SERVER_DATE_FORMAT) > datetime.strptime(self.date_end,DEFAULT_SERVER_DATE_FORMAT):
            raise ValidationError(_('Start date must be smaller then end date !'))
        
        
    @api.onchange('result_selection')
    def select_partner(self):
        """
             This method list out customer and supplier based on selected partner.
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs
             @param context: A standard dictionary

             @return: domain for customer or supplier
        """
        final_res = {}
        res = {}
        if self.result_selection == 'customer':
            res = {'partner_ids' : [('customer','=',True)] }
        elif self.result_selection == 'supplier':
            res = {'partner_ids' : [('supplier','=',True)] }
        else:
            res = {'partnerr_ids' : [] }
        self.partner_ids = []
        final_res.update({'domain':res})
        return final_res
    
    @api.multi
    def print_report(self):
        return self.env['report'].get_action(self, 'baskin_partner_aged_advance_report.report_partner_bal')
    
    
    
    
    
    
    
    

    
