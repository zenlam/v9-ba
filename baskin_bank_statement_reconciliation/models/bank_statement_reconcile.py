# -*- coding: utf-8 -*-

from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from datetime import datetime, date, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.tools.translate import _
from openerp.exceptions import ValidationError, UserError
from openerp.tools.float_utils import float_round
import logging
_logger = logging.getLogger(__name__) 

class bank_statement_reconcile(models.Model):
    _name = "bank.statement.reconcile"
    _inherit = ['mail.thread']
    _description = "Bank Reconcile Reconcile"
    
    @api.depends('bank_recon_number','sequence')
    def get_name_sequence(self):
        for record in self:
            bank_recon_number = ''
            sequence = ''
            if record.bank_recon_number:
                bank_recon_number = record.bank_recon_number 
            if record.sequence:
                sequence = str(record.sequence)
            record.name = bank_recon_number + '-' + sequence
    
    name = fields.Char('Name', compute='get_name_sequence', store=True)
    bank_recon_number = fields.Char('Bank Reconcile Number')
    bank_account_id = fields.Many2one('account.account', domain=[('internal_type','=','liquidity')], string="Bank Account", 
                                      track_visibility='onchange',
                                      required=True)
    currency_id = fields.Many2one('res.currency', string='Currency',required=True, readonly=True)
    actual_bank_statement_date = fields.Date(string='Actual Bank Statement Date', required=True,
                                             help="This is the date appear in the actual bank statement send by bank")
    actual_bank_statement_balance = fields.Float(string='Actual Bank Statement Closing Balance',required=True,
                                                 track_visibility='onchange',
                                                 help="This is the balance as per Bank Statement which stated in bank statement received")
    date_from = fields.Date(string='Show Entries From', required=True, 
                               help="If you only want to show journal items of certain duration, you need this field.",
                               track_visibility='onchange')
    date_end = fields.Date(string='Show Entries As At', required=True, 
                               help="The date selected here will be used to filter all the journal items of this bank account that is still opened for statement reconciliation",
                               track_visibility='onchange')
    date_end_copy = fields.Date(compute='_get_date_end_date' ,string='Show Entries As At')
    balance_till_end = fields.Float(compute='_get_balance_till_end_date', string='System Balance till', store=True)
    opening_balance = fields.Float(string='Opening Balance',track_visibility='onchange')
    closing_balance = fields.Float(string='Closing Balance', store=True)
    difference = fields.Float(compute='_compute_difference', string='Difference (Actual vs System)', store=True)
    
    state = fields.Selection([('draft','Draft'),('validated','Validated')], default="draft", string="Status",track_visibility='onchange')
    sequence = fields.Integer('Sequence', default=1)
    bank_statement_reconcile_line_ids = fields.One2many('bank.statement.reconcile.line', 'bank_statement_id', string="Bank Statement Line")
    bank_statement_reconcile_line_clone_ids = fields.One2many('bank.statement.reconcile.line.clone', 'bank_statement_id', string="Bank Statement Line Clone")
    
    account_move_line_ids = fields.One2many('account.move.line', 'bank_statement_id', string="Account Move Line")
    company_id = fields.Many2one(comodel_name='res.company', string='Company', required=True, index=1, default=lambda self: self.env.user.company_id)
    has_lines = fields.Boolean(compute='_compute_has_lines', string='Has Lines', store=True)
    validate_date = fields.Date(string="Validated On",track_visibility='onchange')
    validate_by = fields.Many2one('res.partner', string="Validated by",track_visibility='onchange')
    internal_note = fields.Text(string="Internal Note")
    
#     @api.multi
#     def name_get(self):
#         result = []
#         for record in self:
#             result.append((record.id, "%s - %s" % (record.bank_account_id.name or '', record.actual_bank_statement_date or '')))
#         return result

    @api.constrains('bank_account_id','state')
    def bank_state_constrain(self):
        if self.bank_account_id and self.state == 'draft':
            other_draft_record = self.search([('id','!=',self.id),
                                              ('bank_account_id','=',self.bank_account_id.id),
                                              ('state','=','draft')])
            name_list = ', '.join([x.name for x in other_draft_record])
            if other_draft_record:
                raise ValidationError(_('Already one Draft bank statement exist for this Bank : %s'%name_list))
    
    @api.constrains('date_from','date_end')
    def date_from_constrain(self):
        if self.date_from and self.date_end:
            
            if datetime.strptime(self.date_from,DEFAULT_SERVER_DATE_FORMAT) > datetime.strptime(self.date_end,DEFAULT_SERVER_DATE_FORMAT):
                raise ValidationError(_('Start date must be smaller then end date !'))
            
            records = self.search([ '&',
                                    '&',
                                    '&',
                                    '|',
                                    '|',
                                    '|',
                                    
                                    '&',
                                    '&',('date_from','>=',self.date_from),('date_from','<=',self.date_end),
                                    '&',('date_end','>=',self.date_from),('date_end','>=',self.date_end),
                                    
                                    '&',
                                    '&',('date_from','<=',self.date_from),('date_from','<=',self.date_end),
                                    '&',('date_end','>=',self.date_from),('date_end','<=',self.date_end),
                                    
                                    '&',
                                    '&',('date_from','<=',self.date_from),('date_from','<=',self.date_end),
                                    '&',('date_end','>=',self.date_from),('date_end','>=',self.date_end),
                                    
                                    '&',
                                    '&',('date_from','>=',self.date_from),('date_from','<=',self.date_end),
                                    '&',('date_end','>=',self.date_from),('date_end','<=',self.date_end),
                                    
                                    ('bank_account_id','=',self.bank_account_id.id),
                                    ('currency_id','=',self.currency_id.id),
                                    ('id','!=',self.id)])
            if records: 
                raise ValidationError("The date selected overlap with one of the record in the system. \n record %s"
                                      %(','.join([str(x.name) for x in records])))

            future_month = self.search(['&',
                                        '&',
                                        '&',
                                    
                                        '&',
                                        '&',('date_from','>=',self.date_from),('date_from','>=',self.date_end),
                                        '&',('date_end','>=',self.date_from),('date_end','>=',self.date_end),
                                        
                                        ('bank_account_id','=',self.bank_account_id.id),
                                        ('currency_id','=',self.currency_id.id),
                                        ('id','!=',self.id)])
            if future_month:
                raise ValidationError("The selected date range is less then one of the record in the system. \n record %s"
                                      %(','.join([str(x.name) for x in future_month])))
                
        elif not self.date_from and self.date_end:
            future_end_date = self.search(['&',
                                        '&',
                                        '&',
                                    
                                        ('date_end','>=',self.date_end),
                                        
                                        ('bank_account_id','=',self.bank_account_id.id),
                                        ('currency_id','=',self.currency_id.id),
                                        ('id','!=',self.id)])
            if future_end_date:
                raise ValidationError("The selected date range is less then one of the record in the system. \n record %s"
                                      %(','.join([str(x.name) for x in future_end_date])))
    @api.depends('account_move_line_ids')
    def _compute_has_lines(self):
        for record in self:
            if len(record.account_move_line_ids.ids) > 0:
                record.has_lines = True
            else:
                record.has_lines = False
        
    
    @api.multi
    def set_to_draft(self):
        for record in self:
            if record.bank_statement_reconcile_line_ids:
                bank_statement_query = """
                   update bank_statement_reconcile_line set bank_state = 'draft' where id in %s
                """
                bank_param = (tuple(record.bank_statement_reconcile_line_ids.ids),)
                self._cr.execute(bank_statement_query,bank_param)
            if record.account_move_line_ids:
                move_line_query = """
                   update account_move_line set bank_state = 'draft' where id in %s
                """
                move_param = (tuple(record.account_move_line_ids.ids),)
                self._cr.execute(move_line_query,move_param)
                
            # bellow part is to delete old clone data for this statement (Use Query considering Huge data)
            delete_old_clone_lines = """
                   delete from bank_statement_reconcile_line_clone where bank_statement_id = %s
                """%record.id
            self._cr.execute(delete_old_clone_lines)
            
            record.state = 'draft'
    
    def get_future_statement(self):
        return self.search([('bank_account_id','=',self.bank_account_id.id),
                            ('currency_id','=',self.currency_id.id),
                            ('sequence','>',self.sequence),
                            ('state','=','validated')], order='sequence asc')
        
    def reset_future_statement(self):
        new_closing = self.closing_balance
        for statement in self.get_future_statement():
            
            statement.opening_balance = new_closing
            statement.actual_bank_statement_balance = statement.closing_balance
            statement.compute_closing_balance()
            new_closing = statement.closing_balance 
    
    @api.multi
    def pre_validate(self):
        for record in self:
            if record.get_future_statement():
                # open wizard and call validate "to prompt user an message about auto update"
                return {
                    'view_id': self.env.ref('baskin_bank_statement_reconciliation.wizard_bank_validate_view').ids,
                    'view_type': 'form',
                    "view_mode": 'form',
                    'res_model': 'bank.validate.wizard',
                    'type': 'ir.actions.act_window',
                    'target': 'new'
                }
            else:
                # call direct validate
                record.validate()
                
        
    @api.multi
    def validate(self):
        for record in self:
            if record.state == 'draft':
                if not record.account_move_line_ids or not record.bank_statement_reconcile_line_ids:
                    raise ValidationError('Dose not have bank statement line to reconcile \n Click on "Load Items" button to reload lines.!')
                if record.currency_id.round(record.difference) != record.currency_id.round(0):
                    raise UserError('Closing balance doesn\'t match with the bank actual balance !')
                # here find all ticked statement lines and mark as matched,
                # and also all move lines related to that line
                bank_line_ids = []
                move_line_ids = []
                for bank_line in record.bank_statement_reconcile_line_ids.filtered(lambda x:x.is_reconcile):
                    bank_line_ids.append(bank_line.id)
                    if bank_line.move_line_id:
                        move_line_ids.append(bank_line.move_line_id.id)
                    else:
                        if not bank_line.move_line_id_string:
                            raise UserError('Something wrong ! \n Looks like journal entry was deleted and it still on this statement so need to Load items again !')
                        for move_line_id in bank_line.move_line_id_string.split(','):
                            if move_line_id:
                                move_line_ids.append(int(move_line_id))
                if len(move_line_ids) != self.env['account.move.line'].search_count([('id','in',move_line_ids),('move_id.state','=','posted')]):
                    raise UserError(
                        'Something wrong ! \n Looks like journal entry was canceled or deleted and it still on this statement so need to Load items again !')

                if bank_line_ids:               
                    bank_statement_query = """
                       update bank_statement_reconcile_line set bank_state = 'match' where id in %s
                    """
                    bank_param = (tuple(bank_line_ids),)
                    self._cr.execute(bank_statement_query,bank_param)
                
                if move_line_ids:
                    move_line_query = """
                       update account_move_line set bank_state = 'match' where id in %s
                    """
                    move_param = (tuple(move_line_ids),)
                    self._cr.execute(move_line_query,move_param)
                
                record.state = 'validated'
                record.validate_date = datetime.now()
                record.validate_by = self.env.user.partner_id.id
                
                record.reset_future_statement()
                
                # bellow part is to delete old clone data for this statement (Use Query considering Huge data)
                delete_old_clone_lines = """
                       delete from bank_statement_reconcile_line_clone where bank_statement_id = %s
                    """%record.id
                self._cr.execute(delete_old_clone_lines)
                
                # bellow part is to copy un-reconciled data to clone model (Use Query considering Huge data)
                copy_data_to_clone_model = """
                       insert into 
                        
                        bank_statement_reconcile_line_clone
                        
                            (is_reconcile ,
                            date ,
                            ref , 
                            memo ,
                            name ,
                            partner_id ,
                            move_line_id ,
                            move_id ,
                            move_line_id_string ,
                            move_id_string , 
                            debit ,
                            credit , 
                            amount_currency,
                            bank_state,
                            company_currency_id,
                            currency_id,
                            bank_statement_id,
                            payment_id)
                        
                        (SELECT 
                            is_reconcile ,
                            date ,
                            ref , 
                            memo ,
                            name ,
                            partner_id ,
                            move_line_id ,
                            move_id ,
                            move_line_id_string ,
                            move_id_string , 
                            debit ,
                            credit , 
                            amount_currency,
                            bank_state,
                            company_currency_id,
                            currency_id,
                            bank_statement_id,
                            payment_id
                            
                        FROM bank_statement_reconcile_line
                        WHERE bank_statement_id = %s
                        AND (is_reconcile is false or is_reconcile is Null)
                        )
                        
                    """%record.id
                self._cr.execute(copy_data_to_clone_model)
                    
                # delete lines which are not reconcile (Use Query considering Huge data)
                delete_bank_draft_line = """
                       delete from bank_statement_reconcile_line where bank_state = 'draft' and bank_statement_id = %s
                    """%record.id
                self._cr.execute(delete_bank_draft_line)
                
                #update original un-match(draft bank_state) move line to de-link from this bank statement (Use Query considering Huge data)
                delink_draft_moveline = """
                       update account_move_line set bank_statement_id = NULL where bank_state = 'draft' and bank_statement_id = %s
                    """%record.id
                self._cr.execute(delink_draft_moveline)
                
            else:
                raise UserError('You can validate draft bank statement only !')
                
#     @api.multi
#     def cancel(self):
#         for record in self:
#             if record.state == 'draft':
#                 self.env['bank.statement.reconcile.line'].search([('bank_statement_id','=',record.id)]).unlink()
#                 self.env['account.move.line'].search([('bank_statement_id','=',record.id)]).write({'bank_statement_id':False})
#                 record.write({'state':'cancelled'})
#             else:
#                 raise UserError('You can not Cancel bank statement other then Draft one !')
    
    @api.model
    def create(self, vals):
        if vals.get('company_id'):
            company =  self.env['res.company'].browse(vals.get('company_id'))
            if company.bank_recon_sequence_id:
                vals['bank_recon_number'] = company.bank_recon_sequence_id.next_by_id()
            else:
                raise UserError(_('Please configure bank reconcile sequence on company settings !'))
        else:
            raise UserError(_('Company is missing !'))
        prev_reconcile_id = self.search([('bank_account_id','=',vals.get('bank_account_id')),
                                         ('currency_id','=',vals.get('currency_id')),
                                         ], order='sequence desc', limit=1)
        
        if prev_reconcile_id:
            vals['sequence'] = prev_reconcile_id.sequence + 1
        else:
            vals['sequence'] = 1
            
        return super(bank_statement_reconcile, self).create(vals)
    
    @api.multi
    def write(self, vals):
        for record in self:
            current_currency_id = False
            if vals.get('currency_id'):
                current_currency_id = vals.get('currency_id')
            else:
                current_currency_id = record.currency_id.id 
            if vals.get('bank_account_id'):
                prev_reconcile_id = self.search([('bank_account_id','=',vals.get('bank_account_id')),
                                                 ('currency_id','=',current_currency_id),
                                                 ], order='sequence desc', limit=1)
                if prev_reconcile_id:
                    vals['sequence'] = prev_reconcile_id.sequence + 1
                else:
                    vals['sequence'] = 1
                
            
        return super(bank_statement_reconcile, self).write(vals)
    
    
    def get_opening_balance(self):
        prev_reconcile_id = self.search([('bank_account_id','=',self.bank_account_id.id),
                                         ('currency_id','=',self.currency_id.id),
                                         ('date_from','<',self.date_from),
                                         ('state','=','validated')
                                         ], order='sequence desc', limit=1)
        if prev_reconcile_id:
            return prev_reconcile_id.closing_balance
        return False
        
        
    @api.depends('date_end')
    def _get_date_end_date(self):
        if self.date_end:
            self.date_end_copy = self.date_end
            
    @api.depends('bank_account_id','date_end')            
    def _get_balance_till_end_date(self):
        """ compute the balance, debit and/or credit for the provided
            account ids
            Arguments:
            `ids`: account ids
            `field_names`: the fields to compute (a list of any of
                           'balance', 'debit' and 'credit')
            `arg`: unused fields.function stuff
            `query`: additional query filter (as a string)
            `query_params`: parameters for the provided query string
                            (__compute will handle their escaping) as a
                            tuple
            """
        for record in self:
            if record.bank_account_id and record.date_end:
                field_names = ['balance','amount_currency']
                # get all the necessary accounts
                children_and_consolidated = record.bank_account_id._get_children_and_consol()
                # compute for each account the balance/debit/credit from the move lines
                accounts = {}
                res = {}
                if children_and_consolidated:
                    date_clouse = """AND (("account_move_line"."date" <= '%s') 
                                     )"""%(record.date_end)
                    request = """
                            SELECT 
                                account_id as id, 
                                COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance,
                                COALESCE(SUM(amount_currency),0) as amount_currency 
                                
                                FROM account_move_line 
                                INNER JOIN account_move ON account_move.id = account_move_line.move_id 
                                WHERE account_id IN %s  
                                {date_clouse}
                                AND bank_state != 'match'
                                AND account_move.state = 'posted'
                                GROUP BY account_id 
    
                    """.format(date_clouse=date_clouse)
                    params = (tuple(children_and_consolidated._ids),) 
                    self._cr.execute(request, params)
        
                    for row in self._cr.dictfetchall():
                        accounts[row['id']] = row
        
                    # consolidate accounts with direct children
                    children_and_consolidated = list(children_and_consolidated.ids)
                    # children_and_consolidated.reverse()
                    list(children_and_consolidated).reverse()
                    brs = list(self.env['account.account'].search([('id','in',children_and_consolidated)], order="id desc"))
                    sums = {}
                    currency_obj = self.env['res.currency']
                    while brs:
                        current = brs.pop(0)
                        for fn in field_names:
                            sums.setdefault(current.id, {})[fn] = accounts.get(current.id, {}).get(fn, 0.0)
                            for child in current.child_id:
                                temp_val = 0
                                if sums.get(child.id) and sums[child.id].get(fn):
                                    temp_val = sums[child.id][fn]
                                elif accounts.get(child.id) and accounts[child.id].get(fn):
                                    temp_val = accounts[child.id][fn]
                                if child.company_id.currency_id.id == current.company_id.currency_id.id:
                                    sums[current.id][fn] += temp_val
                                else:
                                    sums[current.id][fn] += currency_obj.compute(self._cr, self._uid, child.company_id.currency_id.id,
                                                                                 current.company_id.currency_id.id,
                                                                                 temp_val)
        
                            # as we have to relay on values computed before this is calculated separately than previous fields
        
                    res = sums.get(record.bank_account_id.id,{})
                    if record.currency_id and self.env.user.company_id and self.env.user.company_id.currency_id and record.currency_id.id == self.env.user.company_id.currency_id.id:
                        record.balance_till_end = res.get('balance', 0.0)
                    else:
                        record.balance_till_end = res.get('amount_currency', 0.0)
                        
        
    @api.onchange('date_from')
    def onchange_date_from(self):
        if self.bank_account_id and self.date_from:
            self.opening_balance =  self.get_opening_balance()
        else:
            self.opening_balance = False
        
    @api.onchange('bank_account_id')
    def onchange_bank_account_id(self):
        if self.bank_account_id and self.bank_account_id.currency_id:
            self.currency_id = self.bank_account_id.currency_id.id
        elif self.env.user.company_id and self.env.user.company_id.currency_id:
            self.currency_id = self.env.user.company_id.currency_id.id
        
        if self.bank_account_id and self.date_from:
            self.opening_balance =  self.get_opening_balance() 
        else:
            self.opening_balance = False
    
    @api.multi
    def unlink(self):
        for record in self:
            if record.state == 'validated':
                raise UserError(_('You can not delete already reconciled bank statement !'))
        return super(bank_statement_reconcile, self).unlink()
    
    @api.multi
    def compute_closing_balance(self):
        _logger.info("start............")
        for record in self:
            self._get_balance_till_end_date()
            _logger.info('id--------%s'%record.id)
            total_closing_bal = record.currency_id.round(0)
            if record.opening_balance:
                total_closing_bal += record.currency_id.round(record.opening_balance)
            select_credit_total = """
                select 
                COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance,
                COALESCE(SUM(credit), 0) as credit,
                COALESCE(SUM(debit), 0) as debit,
                COALESCE(SUM(amount_currency), 0) as amount_currency
                
                from bank_statement_reconcile_line
                
                where is_reconcile = True
                and bank_statement_id = %s
            """%record.id
            
            self._cr.execute(select_credit_total)
            for row in self._cr.dictfetchall():
                # base currency
                if record.currency_id and self.env.user.company_id and self.env.user.company_id.currency_id and record.currency_id.id == self.env.user.company_id.currency_id.id:
                    total_closing_bal += record.currency_id.round(row['balance'])
                # foreign currency
                elif self.currency_id:
                    total_closing_bal += record.currency_id.round(row['amount_currency'])
            
            _logger.info("end............")
            record.closing_balance = total_closing_bal
        
    @api.depends('closing_balance','actual_bank_statement_balance')
    def _compute_difference(self):
        for record in self:
            closing_balance = record.closing_balance or 0
            actual_bank_statement_balance = record.actual_bank_statement_balance or 0
            record.difference = record.currency_id.round(record.currency_id.round(closing_balance) - record.currency_id.round(actual_bank_statement_balance))

        
    @api.one
    def load_items(self):
        self.closing_balance = 0
        # get all ticked line move_id , move_line_id , move_line_id_string, move_id_string
        # concat all this four and make unique list of all the line ids
        select_ticked_line = """
               select coalesce(move_id::text,'') || coalesce(move_line_id::text,'') || coalesce(move_id_string,'') || coalesce(move_line_id_string,'')  as unique_id
               from 
               bank_statement_reconcile_line 
               where bank_statement_id = %s
                       and is_reconcile = True
               
            """%self.id
        self._cr.execute(select_ticked_line)
        ticked_line_ids = []
        for row in self._cr.dictfetchall():
            ticked_line_ids.append(str(row['unique_id'])) 
        # delete all lines then add fresh again (Use Query considering Huge data)
        delete_all_line = """
               delete from bank_statement_reconcile_line where bank_statement_id = %s
            """%self.id
        self._cr.execute(delete_all_line)
        
        # de-link all original move line from bank statement (Use Query considering Huge data)
        update_statement_id = """
                       update account_move_line set bank_statement_id = NULL where bank_statement_id = %s
                    """ % self.id
        self._cr.execute(update_statement_id)

        delink_all_move_line = """
               update bank_statement_reconcile_line set bank_statement_id = NULL where bank_statement_id = %s
            """%self.id
        self._cr.execute(delink_all_move_line)
        
        currency_clause = ''
        # if self.currency_id and self.env.user.company_id and self.env.user.company_id.currency_id and self.currency_id.id == self.env.user.company_id.currency_id.id:
        #     currency_clause = 'AND aml.currency_id is null'
        # elif self.currency_id:
        #     currency_clause = 'AND aml.currency_id = %s'%self.currency_id.id
            
        if self.bank_account_id and self.date_end:
            # get all the necessary accounts
            children_and_consolidated = self.bank_account_id._get_children_and_consol()
            # compute for each account the balance/debit/credit from the move lines
            if children_and_consolidated:
                date_clouse = ""
#                 if self.date_from and self.date_end:
#                     date_clouse = """AND (("aml"."date" <= '%s') 
#                                      AND  ("aml"."date" >= '%s'))"""%(self.date_end,self.date_from)
                if self.date_end:
                    date_clouse = """AND (("aml"."date" <= '%s') 
                                     )"""%(self.date_end)
                request = """
                        insert into 
                        
                        bank_statement_reconcile_line
                        
                            (date ,
                            ref ,
                            memo , 
                            name ,
                            partner_id ,
                            move_line_id ,
                            move_id ,
                            debit ,
                            credit ,
                            amount_currency , 
                            bank_state ,
                            company_currency_id , 
                            currency_id,
                            bank_statement_id)
                        
                        (SELECT 
                            aml.date as date,
                            aml.ref as ref,
                            account_move.memo as memo,
                            aml.name as name,
                            aml.partner_id as partner_id,
                            aml.id as move_line_id,
                            aml.move_id as move_id,
                            COALESCE(aml.debit, 0) as debit ,
                            COALESCE(aml.credit, 0) as credit,
                            COALESCE(aml.amount_currency, 0) as amount_currency,
                            aml.bank_state as bank_state,
                            aml.company_currency_id as company_currency_id,
                            aml.currency_id as currency_id,
                            {bank_statement_id}
                            
                        FROM account_move_line aml 
                        INNER JOIN account_move ON account_move.id = aml.move_id 
                        
                        WHERE aml.account_id IN %s  
                        {date_clouse}
                        AND aml.bank_state != 'match'
                        AND account_move.state = 'posted'
                        AND (aml.payment_via != 'bulk' or aml.payment_via is null)
                        {currency_clause}
                        )
                        
                        RETURNING *
                            
                """.format(date_clouse=date_clouse,bank_statement_id=self.id,currency_clause=currency_clause)
                params = (tuple(children_and_consolidated._ids),) 
                print "query 1 ---> ",request,params
                self._cr.execute(request, params)
                normal_line_ids = []
                for row in self._cr.dictfetchall():
                    normal_line_ids.append(row['move_line_id'])
                                        
                
                
                bulk_payment_query = """
                        insert into 
                        
                        bank_statement_reconcile_line
                        
                            (date ,
                            ref ,
                            memo , 
                            name ,
                            partner_id ,
                            move_line_id_string ,
                            move_id_string ,
                            debit ,
                            credit ,
                            amount_currency , 
                            bank_state ,
                            company_currency_id ,
                            currency_id,
                            payment_id, 
                            bank_statement_id)
                        (SELECT 
                            aml.date as date,
                            array_to_string(array_agg(ARRAY[aml.ref]),', ') as ref,
                            account_move.memo as memo,
                            aml.name as name,
                            aml.partner_id as partner_id,
                            array_to_string(array_agg(ARRAY[aml.id] ORDER BY aml.id),', ') as move_line_id_string,
                            array_to_string(array_agg(ARRAY[aml.move_id] ORDER BY aml.move_id),', ') as move_id_string,
                            COALESCE(sum(aml.debit), 0) as debit ,
                            COALESCE(sum(aml.credit), 0) as credit,
                            COALESCE(sum(aml.amount_currency), 0) as amount_currency,
                            aml.bank_state as bank_state,
                            aml.company_currency_id as company_currency_id,
                            aml.currency_id as currency_id,
                            aml.payment_id,
                            {bank_statement_id}
                            
                            
                        FROM account_move_line aml 
                        INNER JOIN account_move ON account_move.id = aml.move_id 
                        
                        WHERE aml.account_id IN %s  
                        {date_clouse}
                        AND aml.bank_state != 'match'
                        AND account_move.state = 'posted'
                        AND aml.payment_via = 'bulk'
                        {currency_clause}
                        
                        group by aml.payment_id,aml.date,account_move.memo,aml.name,aml.partner_id,aml.bank_state,aml.currency_id,aml.company_currency_id )
                        
                        RETURNING *
                """.format(date_clouse=date_clouse,bank_statement_id=self.id,currency_clause=currency_clause)
                self._cr.execute(bulk_payment_query, params)
                print "query 2 ---> ",bulk_payment_query,params
                bulk_normal_line_ids = []
                for row in self._cr.dictfetchall():
                    for line_id in row['move_line_id_string'].split(','):
                        if line_id:
                            bulk_normal_line_ids.append(int(line_id))
                    
                _logger.info('bulk_normal_line_ids--- %s'%bulk_normal_line_ids)
                    
                # self.env['account.move.line'].browse( normal_line_ids + bulk_normal_line_ids ).write({'bank_statement_id':self.id})
                if normal_line_ids + bulk_normal_line_ids:
                    update_statement_id_new = """
                                           update account_move_line set bank_statement_id = %s where id in %s
                                        """
                    self._cr.execute(update_statement_id_new, (self.id, tuple(normal_line_ids + bulk_normal_line_ids),) )
                
                if ticked_line_ids:
                    ticked_line_ids.append('hack_element')
                    # after fetching new lines ticked lines which are ticked in old list
                    mark_tick_as_old_lines = """
                           update bank_statement_reconcile_line 
                           set is_reconcile = True
                           where bank_statement_id = %s 
                                   and
                                   coalesce(move_id::text,'') || coalesce(move_line_id::text,'') || coalesce(move_id_string,'') || coalesce(move_line_id_string,'') in %s
                                   
                           
                        """%(self.id,tuple(ticked_line_ids),)
                    self._cr.execute(mark_tick_as_old_lines)
                