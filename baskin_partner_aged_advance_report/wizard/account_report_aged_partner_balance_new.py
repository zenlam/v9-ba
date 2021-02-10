# -*- coding: utf-8 -*-

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError
from openerp.tools import float_is_zero
from cStringIO import StringIO
import xlsxwriter
import base64
from operator import itemgetter
import logging
_logger = logging.getLogger(__name__)

def merge_two_dicts(x, y):
    z = x.copy()   # start with x's keys and values
    z.update(y)    # modifies z with y's keys and values & returns None
    return z

class account_aged_trial_balance_new(models.TransientModel):
    """
    This wizard will provide the selected Periods and Partner based on the generate the aged partner balance report.
    """
    _inherit = 'account.common.partner.report'
    _name = 'account.aged.trial.balance.new'
    _description = 'Account Aged Trial balance Report New'
    
    date_from = fields.Date(string='Start Date', default=lambda *a: time.strftime('%Y-%m-%d'))
    period_length = fields.Integer('Period Length (days)', default=30, required=True)
    direction_selection = fields.Selection([('past','Past'),
                                             ('future','Future')],
                                             'Analysis Direction', default='past', required=True)
    partner_ids = fields.Many2many('res.partner','aging_rel_partner','partner_id','parent_id','Partner')
    page_split = fields.Boolean('One Partner Per Sheet', help='Display Report with One partner per Sheet')
    currency_selection = fields.Selection([('base_currency','Base Currency'),
                                           ('foreign_currency','Foreign Currency')],
                                           'Currency', default='base_currency', required=True)
    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)
    report_type = fields.Selection([
                    ('detail', 'Detail'),
                    ('summary', 'Summary')
                ], string='Report Type', default='detail')
    
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
    def _print_report(self, data):
        """
             To print report.

             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs
             @param context: A standard dictionary

             @return: Report action
        """

        res = {}
        data = self.pre_print_report(data)
        data['form'].update(self.read(['period_length', 'direction_selection','partner_ids', 'page_split', 'currency_selection', 'report_type'])[0])
        period_length = data['form']['period_length']
        
        if data['form'].get('partner_ids') and len(data['form'].get('partner_ids')) > 20:
            raise UserError(_('You can not select more then 20 Customer/Supplier.'))
        
        if period_length<=0:
            raise UserError(_('You must set a period length greater than 0.'))
        if not data['form']['date_from']:
            raise UserError(_('You must set a start date.'))
        start = datetime.strptime(data['form']['date_from'], "%Y-%m-%d")
#        period_length = 30
        if data['form']['direction_selection'] == 'past':
            for i in range(5)[::-1]:
                stop = start - relativedelta(days=period_length - 1)

                if i == 4:
                    res[str(i)] = {
                        'name': (i!=0 and (str((5-(i+1)) * period_length) + '-' + str((5-i) * period_length)) or ('+'+str((4 * period_length)))),
                        'stop': start.strftime('%Y-%m-%d'),
                        'start': (i!=0 and stop.strftime('%Y-%m-%d') or False),
                    }
                else:
                    res[str(i)] = {
                        'name': (i!=0 and (str(((5-(i+1)) * period_length)+1) + '-' + str((5-i) * period_length)) or ('+'+str((4 * period_length)+1))),
                        'stop': start.strftime('%Y-%m-%d'),
                        'start': (i!=0 and stop.strftime('%Y-%m-%d') or False),
                    }
                start = stop - relativedelta(days=1)
        else:
            for i in range(5):
                stop = start + relativedelta(days=period_length -1)
                if i == 0:
                    res[str(5-(i+1))] = {
                        'name': (i!=4 and str((i) * period_length)+'-' + str((i+1) * period_length) or ('+'+str(4 * period_length))),
                        'start': start.strftime('%Y-%m-%d'),
                        'stop': (i!=4 and stop.strftime('%Y-%m-%d') or False),
                    }
                else:
                    res[str(5-(i+1))] = {
                        'name': (i!=4 and str(((i) * period_length)+1)+'-' + str((i+1) * period_length) or ('+'+str((4 * period_length)+1))),
                        'start': start.strftime('%Y-%m-%d'),
                        'stop': (i!=4 and stop.strftime('%Y-%m-%d') or False),
                    }
                start = stop + relativedelta(days=1)
        
        data['form'].update(res)
        return self.print_xls(data)
    
    def _get_partner_move_lines(self, form, account_type, date_from, target_move):
        res = []
        self.total_account = []
        cr = self.env.cr
        user_company = self.env.user.company_id.id
        move_state = ['draft', 'posted']
        if target_move == 'posted':
            move_state = ['posted']
        arg_list = (tuple(move_state), tuple(account_type))
        #build the reconciliation clause to see what partner needs to be printed
        
        reconciliation_clause = '(l.reconciled IS FALSE)'
        if self.direction_selection == 'future':
            cr.execute('SELECT debit_move_id, credit_move_id FROM account_partial_reconcile where create_date > %s', (date_from,))
        elif self.direction_selection == 'past': # Using elif so people could extend without this breaking
            cr.execute('SELECT debit_move_id, credit_move_id FROM account_partial_reconcile where create_date > %s', (date_from,))
        reconciled_after_date = []
        for row in cr.fetchall():
            reconciled_after_date += [row[0], row[1]]
        if reconciled_after_date:
            reconciliation_clause = '(l.reconciled IS FALSE OR l.id IN %s)'
            arg_list += (tuple(reconciled_after_date),)
        
        arg_list += (date_from, user_company, tuple(form.get('partner_ids')))
        
        foreign = False
        currency_select = ', rc.name as currency_name'
        currency_table = 'left join res_currency as rc on rc.id = l.company_currency_id'
        currency_condition = ''
        if self.currency_selection == 'foreign_currency':
            foreign = True
            currency_select = ', rc.name as currency_name'
            currency_table = 'left join res_currency as rc on rc.id = l.currency_id AND l.currency_id is not null'
            currency_condition = 'AND l.currency_id is not null'

        if self.direction_selection == 'future':
            line_date_condition = '(l.date <= %s)'
            line_date_maturity_condition = '(COALESCE(l.date_maturity, l.date) < %s)'
        elif self.direction_selection == 'past': 
            line_date_condition = '(l.date <= %s)'
            line_date_maturity_condition = '(COALESCE(l.date_maturity,l.date) > %s)'
        
        # Note: here we do union query to get the data of invoice and Payment as separate.
        # So invoice id column is have id of invoice as well as payment.
        
        query = '''
                SELECT * from (
                    SELECT DISTINCT res_partner.id AS id, res_partner.name AS name, UPPER(res_partner.name) AS uppername,
                    a.actual_invoice_date::text as actual_invoice_date, 
                    a.payment_term_id AS payment_term_id, 
                    a.name AS memo,
                    l.date AS date, 
                    am.ref as move_ref, 
                    am.name AS ref,
                    account_account.code AS code ''' \
                    + currency_select + ''', 
                    l.id AS line_id,
                    l.move_id,
                    
                    case 
                        when a.id is not null then
                            'INV_'||a.id::text 
                        when payment.id is not null then
                            'PYMT_'||payment.id::text
                        else
                            l.id::text 
                    end as inv_id,    
                    
                    
                    payment.payment_via as payment_via \
                    
                    FROM res_partner
                    left join account_move_line AS l on l.partner_id = res_partner.id
                    left join account_account on l.account_id = account_account.id
                    left join account_move am on l.move_id = am.id
                    ''' + currency_table + '''
                    left join account_invoice as a on a.move_id = l.move_id
                    left join account_payment payment on payment.id = l.payment_id 
                    WHERE 
                        
                        am.state IN %s
                        AND account_account.internal_type IN %s
                        AND ''' + reconciliation_clause + '''
                        
                        AND ''' + line_date_condition + '''
                        AND l.company_id = %s
                        AND (l.partner_id in %s)
                    
                    ) as DATA
                ORDER BY UPPER(DATA.name)''' 
        cr.execute(query, arg_list )
        

        partners = cr.dictfetchall()
        #print "partners custom ==>",partners
        # put a total of 0
        for i in range(7):
            self.total_account.append(0)

        # Build a string like (1,2,3) for easy use in SQL query
        partner_ids = list(set([partner['id'] for partner in partners]))
        if not partner_ids:
            return []

        #print "partner_ids",partner_ids
        
        # This dictionary will store the future or past of all partners
        future_past = {}
        def get_inv_id(id):
            return 'INV_'+str(id)
        def get_pymt_id(id):
            return 'PYMT_'+str(id)
         
        args_list2 = (tuple(move_state), 
                         tuple(account_type), 
                         self.date_from, 
                         tuple(partner_ids),
                         self.date_from, 
                         user_company)

            
        query = '''SELECT l.partner_id,l.id AS line_id,l.move_id,'INV_'||a.id::text AS inv_id
                        FROM account_move_line AS l 
                        left join account_account on l.account_id=account_account.id
                        left join account_move am on l.move_id=am.id
                        left join account_invoice a  on a.move_id = l.move_id 
                        left join account_payment payment on payment.id = l.payment_id 
                                                        and  payment.payment_via in ('normal','deposit','adv_payment')
                        WHERE 
                        
                        am.state IN %s
                        AND (account_account.internal_type IN %s)
                        AND ''' + line_date_maturity_condition +'''
                        AND (l.partner_id IN %s)
                        AND ''' + line_date_condition + '''
                        AND l.company_id = %s
                        ''' + currency_condition + '''
                        
                        GROUP BY l.partner_id,l.id,l.move_id,a.id,payment.id
                    
                    '''
        
        cr.execute(query,args_list2)
        t = cr.fetchall()
        #print "query 2 t --->",t
#         for i in t:
#             future_past[i[-1]] = i[1]

            
        aml_ids = t and [x[1] for x in t] or []
        for line in self.env['account.move.line'].browse(aml_ids):
            dict_key_id = False
            if line.invoice_id:
                dict_key_id = get_inv_id(line.invoice_id.id)
            elif line.payment_id:
                dict_key_id = get_pymt_id(line.payment_id.id)
            else:
                dict_key_id = str(line.id)
            if line.invoice_id and line.payment_id:
                raise ValidationError('Account move line link with payment and invoice both !')
            if dict_key_id not in future_past:
                future_past[dict_key_id] = 0.0
            line_amount = foreign and line.amount_currency or line.balance
            if not foreign and line.balance == 0:
                continue
            if foreign and line.amount_currency == 0:
                continue
            if self.direction_selection == 'future':
                for partial_line in line.matched_debit_ids:
                    if partial_line.create_date[:10] >= self.date_from:
                        line_amount += partial_line.amount_currency if foreign else partial_line.amount
                for partial_line in line.matched_credit_ids:
                    if partial_line.create_date[:10] >= self.date_from:
                        line_amount -= partial_line.amount_currency if foreign else partial_line.amount
            elif self.direction_selection == 'past': # Using elif so people could extend without this breaking
                for partial_line in line.matched_debit_ids:
                    if partial_line.create_date[:10] <= self.date_from:
                        line_amount += partial_line.amount_currency if foreign else partial_line.amount
                for partial_line in line.matched_credit_ids:
                    if partial_line.create_date[:10] <= self.date_from:
                        line_amount -= partial_line.amount_currency if foreign else partial_line.amount
            future_past[dict_key_id] += line_amount
            

        # print "future_past custom===>",future_past
        # Use one query per period and store results in history (a list variable)
        # Each history will contain: history[1] = {'<partner_id>': <partner_debit-credit>}
        history = []
        for i in range(5):
            #print "form[str(i)--->",form[str(i)]
            if reconciled_after_date:
                args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            else:
                args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            dates_query = '(COALESCE(l.date_maturity,l.date)'
            if form[str(i)]['start'] and form[str(i)]['stop']:
                dates_query += ' BETWEEN %s AND %s)'
                args_list += (form[str(i)]['start'], form[str(i)]['stop'])
            elif form[str(i)]['start']:
                dates_query += ' >= %s)'
                args_list += (form[str(i)]['start'],)
            else:
                dates_query += ' <= %s)'
                args_list += (form[str(i)]['stop'],)
            args_list += (date_from, user_company)

            query = '''SELECT l.partner_id, l.id AS line_id,l.move_id,'INV_'||a.id::text AS inv_id\
                        FROM account_move_line AS l 
                        left join account_account on l.account_id = account_account.id
                        left join account_move am on l.move_id = am.id
                        left join account_invoice a on a.move_id = l.move_id 
                        left join account_payment payment on payment.id = l.payment_id and payment.payment_via in ('normal','deposit','adv_payment')
                        WHERE 
                            
                            (am.state IN %s)
                            AND (account_account.internal_type IN %s)
                            AND (l.partner_id IN %s)
                            AND ''' + dates_query + '''
                            ''' + currency_condition + '''
                        AND ''' + line_date_condition + '''
                        AND l.company_id = %s
                        GROUP BY l.partner_id,l.id,l.move_id,a.id ,payment.id
                        '''
            # print "query history ===> ",query, args_list

            cr.execute(query, args_list)
            partners_partial = cr.fetchall()
            #print "partners_partial-->",partners_partial
            partners_amount = dict((i[-1],0) for i in partners_partial)
            
            aml_ids = partners_partial and [x[1] for x in partners_partial] or []
            for line in self.env['account.move.line'].browse(aml_ids):
                dict_key_id = False
                if line.invoice_id:
                    dict_key_id = get_inv_id(line.invoice_id.id)
                elif line.payment_id:
                    dict_key_id = get_pymt_id(line.payment_id.id)
                else:
                    dict_key_id = str(line.id)



                if dict_key_id not in partners_amount:
                    partners_amount[dict_key_id] = 0.0
                line_amount = foreign and line.amount_currency or line.balance
                if not foreign and line.balance == 0:
                    continue
                if foreign and line.amount_currency == 0:
                    continue
                if self.direction_selection == 'future':
                    for partial_line in line.matched_debit_ids:
                        if partial_line.create_date[:10] >= self.date_from:
                            line_amount += partial_line.amount_currency if foreign else partial_line.amount
                    for partial_line in line.matched_credit_ids:
                        if partial_line.create_date[:10] >= self.date_from:
                            line_amount -= partial_line.amount_currency if foreign else partial_line.amount
                elif self.direction_selection == 'past': # Using elif so people could extend without this breaking
                    for partial_line in line.matched_debit_ids:
                        if partial_line.create_date[:10] <= self.date_from:
                            line_amount += partial_line.amount_currency if foreign else partial_line.amount
                    for partial_line in line.matched_credit_ids:
                        if partial_line.create_date[:10] <= self.date_from:
                            line_amount -= partial_line.amount_currency if foreign else partial_line.amount
                partners_amount[dict_key_id] += line_amount


            # Note here merge two dictionary and then append (for invoice and payment)
            # to have only FIVE dictionary in list
            history.append(partners_amount)

#             for partner_info in partners_partial:
#                 partners_amount[partner_info[-1]] = partner_info[1]
#             history.append(partners_amount)
        already_prceed_ids = []
        for partner in partners:

            if partner['inv_id'] not in already_prceed_ids:
                already_prceed_ids.append(partner['inv_id'])
#                 _logger.info("partner inv/payment id ------- %s"%partner['inv_id'])
                at_least_one_amount = False
                values = {}
                
                ## If choise selection is in the future
                if self.direction_selection == 'future':
                    # Query here is replaced by one query which gets the all the partners their 'before' value
                    before = False
                    if future_past.has_key(partner['inv_id']):
                        before = [ future_past[partner['inv_id']] ]
                    self.total_account[6] = self.total_account[6] + (before and before[0] or 0.0)
                    values['direction'] = before and before[0] or 0.0
                elif self.direction_selection == 'past': # Changed this so people could in the future create new direction_selections
                    # Query here is replaced by one query which gets the all the partners their 'after' value
                    after = False
                    if future_past.has_key(partner['inv_id']): # Making sure this partner actually was found by the query
                        after = [ future_past[partner['inv_id']] ]
    
                    self.total_account[6] = self.total_account[6] + (after and after[0] or 0.0)
                    values['direction'] = after and after[0] or 0.0
                
                if not float_is_zero(values['direction'], precision_rounding=self.env.user.company_id.currency_id.rounding):
                    at_least_one_amount = True
    
                for i in range(5):
                    during = False
                    if history[i].has_key(partner['inv_id']):
                        during = [history[i][partner['inv_id']]]
                    # Adding counter
                    self.total_account[(i)] = self.total_account[(i)] + (during and during[0] or 0)
                    values[str(i)] = during and during[0] or 0.0
                    if not float_is_zero(values[str(i)], precision_rounding=self.env.user.company_id.currency_id.rounding):
                        at_least_one_amount = True
                values['total'] = sum([values['direction']] + [values[str(i)] for i in range(5)])
                ## Add for total
                self.total_account[(i + 1)] += values['total']
                values['name'] = partner['name']
                payment_term = False
                if partner['payment_term_id']:
                    payment_term = self.env['account.payment.term'].browse(partner['payment_term_id']).name
                values['payment_term'] = payment_term
                values['date'] = partner['date']
                values['ref'] = partner['ref']
                values['move_ref'] = partner['move_ref']
                values['actual_invoice_date'] = partner['actual_invoice_date']
                values['code'] = partner['code']
                values['memo'] = partner['memo']
                values['currency_name'] = partner.get('currency_name') or ''
                values['partner_id'] = partner['id']
                values['payment_via'] = partner['payment_via']

                if at_least_one_amount:
                    if self._context and self._context.get('statement_end_date') and self._context.get('is_partner_balance'):
                        if partner['date']:
                            line_date = datetime.strptime(partner['date'],DEFAULT_SERVER_DATE_FORMAT)
                            statement_end_date = datetime.strptime(self._context['statement_end_date'],DEFAULT_SERVER_DATE_FORMAT)
                            if line_date < statement_end_date:
                                res.append(values)
                    else:
                        res.append(values)
        
        #print "===>res",res
        total = 0.0
        totals = {}
        new_dict_data = []
        for r in res:
            total += float(r['total'] or 0.0)
            for i in range(5) + ['direction']:
                totals.setdefault(str(i), 0.0)
                totals[str(i)] += float(r[str(i)] or 0.0)
        #print "res==>",res
        if form.get('page_split'):
            old_data = res
            new_data = self.prepare_data_format(old_data)
            for d in old_data:
                direction = 0.0
                four = 0.0
                three = 0.0
                two = 0.0
                one = 0.0
                zero = 0.0
                for dd in new_data:
                    if dd and dd.has_key('partner_id') and dd.get('partner_id') == d.get('partner_id'):
                        temp_list = dd.get('info')
                        temp_list.append(d)
                        dd.update({'info':temp_list})
                        if dd.has_key('info') and dd.get('partner_id') == d.get('partner_id'):
                            final_tot = 0.0
                            for tmp in dd.get('info'):
                                direction += tmp['direction']
                                four += tmp['4']
                                three += tmp['3']
                                two += tmp['2']
                                one += tmp['1']
                                zero += tmp['0']
                                final_tot += tmp['direction']
                                final_tot += tmp['4']
                                final_tot += tmp['3']
                                final_tot += tmp['2']
                                final_tot += tmp['1']
                                final_tot += tmp['0']
                                dd.update({'final_total':final_tot,
                                           'dir':direction,
                                           'four':four,
                                           'three': three,
                                           'two': two,
                                           'one': one,
                                           'zero':zero})

            for dic_data in new_data:
                new_info_data = []
                for data in dic_data['info']:
                    data_dict = self._prepare_total_dict_data(data)
                    new_info_data.append(data_dict)
                dic_data['info'] = new_info_data
                new_dict_data.append(dic_data)
            #print "new_dict_data--- with split=",new_dict_data
            return new_dict_data
        else:
            for data in res:
                data_dict = self._prepare_total_dict_data(data)
                new_dict_data.append(data_dict)
            #print "new_dict_data--- withOUT split=",new_dict_data
            return new_dict_data
        return []
      
    def _prepare_total_dict_data(self, dict_info):
        standard_keys = ['direction', '0','1','2','3','4']
        temp_dict = dict_info.copy()
        final_total = 0.0
        for key,val in temp_dict.iteritems():
            if key in standard_keys:
                final_total += val
                temp_dict.update({'total':final_total})
        return temp_dict

    def prepare_data_format(self,old_data):
        final_data = []
        partner_ids = []
        for data in old_data:
            if data.get('partner_id') not in partner_ids:
                final_data.append({'partner_id':data.get('partner_id'), 'info':[], 'final_total':0.0})
                partner_ids.append(data.get('partner_id'))
        return final_data

    def _get_partner_summary_move_lines(self, form, account_type, date_from, target_move):
        Partner = self.env['res.partner']
        res = []
        self.total_account = []
        cr = self.env.cr
        user_company = self.env.user.company_id.id
        move_state = ['draft', 'posted']
        if target_move == 'posted':
            move_state = ['posted']
        arg_list = (tuple(move_state), tuple(account_type))
        # build the reconciliation clause to see what partner needs to be printed

        reconciliation_clause = '(l.reconciled IS FALSE)'
        if self.direction_selection == 'future':
            cr.execute('SELECT debit_move_id, credit_move_id FROM account_partial_reconcile where create_date > %s', (date_from,))
        elif self.direction_selection == 'past':  # Using elif so people could extend without this breaking
            cr.execute('SELECT debit_move_id, credit_move_id FROM account_partial_reconcile where create_date > %s', (date_from,))
        reconciled_after_date = []
        for row in cr.fetchall():
            reconciled_after_date += [row[0], row[1]]
        if reconciled_after_date:
            reconciliation_clause = '(l.reconciled IS FALSE OR l.id IN %s)'
            arg_list += (tuple(reconciled_after_date),)

        partner_ids = []
        if form.get('partner_ids'):
            partner_ids = form.get('partner_ids')
        else:
            if form['result_selection'] == 'customer':
                partner_ids = Partner.search([('customer', '=', True)]).ids
            elif form['result_selection'] == 'supplier':
                partner_ids = Partner.search([('supplier', '=', True)]).ids
            else:
                partner_ids = Partner.search(['|', ('customer', '=', True), ('supplier', '=', True)]).ids

        arg_list += (date_from, user_company, tuple(partner_ids))

        foreign = False
        currency_select = ', rc.name as currency_name'
        currency_table = 'left join res_currency as rc on rc.id = l.company_currency_id'
        currency_condition = ''
        if self.currency_selection == 'foreign_currency':
            foreign = True
            currency_select = ', rc.name as currency_name'
            currency_table = 'left join res_currency as rc on rc.id = l.currency_id AND l.currency_id is not null'
            currency_condition = 'AND l.currency_id is not null'

        if self.direction_selection == 'future':
            line_date_condition = '(l.date <= %s)'
            line_date_maturity_condition = '(COALESCE(l.date_maturity, l.date) < %s)'
        elif self.direction_selection == 'past':
            line_date_condition = '(l.date <= %s)'
            line_date_maturity_condition = '(COALESCE(l.date_maturity,l.date) > %s)'

        # Note: here we do union query to get the data of invoice and Payment as separate.
        # So invoice id column is have id of invoice as well as payment.

        query = '''
                SELECT * from (
                    SELECT DISTINCT res_partner.id AS id, res_partner.name AS name, UPPER(res_partner.name) AS uppername,
                    a.actual_invoice_date::text as actual_invoice_date,
                    a.payment_term_id AS payment_term_id,
                    l.date AS date,
                    am.ref as move_ref,
                    am.name AS ref,
                    account_account.code AS code ''' \
                    + currency_select + ''',
                    l.id AS line_id,
                    l.move_id,
                    case
                        when a.id is not null then
                            'INV_'||a.id::text
                        when payment.id is not null then
                            'PYMT_'||payment.id::text
                        else
                            l.id::text
                    end as inv_id,
                    payment.payment_via as payment_via \
                    FROM res_partner
                    left join account_move_line AS l on l.partner_id = res_partner.id
                    left join account_account on l.account_id = account_account.id
                    left join account_move am on l.move_id = am.id
                    ''' + currency_table + '''
                    left join account_invoice as a on a.move_id = l.move_id
                    left join account_payment payment on payment.id = l.payment_id
                    WHERE
                        am.state IN %s
                        AND account_account.internal_type IN %s
                        AND ''' + reconciliation_clause + '''
                        AND ''' + line_date_condition + '''
                        AND l.company_id = %s
                        AND (l.partner_id in %s)
                    ) as DATA
                ORDER BY UPPER(DATA.name)'''
        cr.execute(query, arg_list)
        partners = cr.dictfetchall()
        # put a total of 0
        for i in range(7):
            self.total_account.append(0)
        # Build a string like (1,2,3) for easy use in SQL query
        partner_ids = list(set([partner['id'] for partner in partners]))
        if not partner_ids:
            return []

        # This dictionary will store the future or past of all partners
        future_past = {}

        def get_inv_id(id):
            return 'INV_'+str(id)

        def get_pymt_id(id):
            return 'PYMT_'+str(id)

        args_list2 = (tuple(move_state),
                      tuple(account_type),
                      self.date_from,
                      tuple(partner_ids),
                      self.date_from,
                      user_company)

        query = '''SELECT l.partner_id,l.id AS line_id,l.move_id,'INV_'||a.id::text AS inv_id
                    FROM account_move_line AS l
                    left join account_account on l.account_id=account_account.id
                    left join account_move am on l.move_id=am.id
                    left join account_invoice a on a.move_id = l.move_id
                    left join account_payment payment on payment.id = l.payment_id
                            and  payment.payment_via in ('normal','deposit','adv_payment')
                    WHERE
                        am.state IN %s
                        AND (account_account.internal_type IN %s)
                        AND ''' + line_date_maturity_condition + '''
                        AND (l.partner_id IN %s)
                        AND ''' + line_date_condition + '''
                        AND l.company_id = %s
                        ''' + currency_condition + '''
                        GROUP BY l.partner_id,l.id,l.move_id,a.id,payment.id
                    '''
        cr.execute(query, args_list2)
        t = cr.fetchall()
#         for i in t:
#             future_past[i[-1]] = i[1]
        aml_ids = t and [x[1] for x in t] or []
        for line in self.env['account.move.line'].browse(aml_ids):
            dict_key_id = line.partner_id.id
            if dict_key_id not in future_past:
                future_past[dict_key_id] = 0.0
            line_amount = foreign and line.amount_currency or line.balance
            if not foreign and line.balance == 0:
                continue
            if foreign and line.amount_currency == 0:
                continue
            if self.direction_selection == 'future':
                for partial_line in line.matched_debit_ids:
                    if partial_line.create_date[:10] >= self.date_from:
                        line_amount += partial_line.amount_currency if foreign else partial_line.amount
                for partial_line in line.matched_credit_ids:
                    if partial_line.create_date[:10] >= self.date_from:
                        line_amount -= partial_line.amount_currency if foreign else partial_line.amount
            elif self.direction_selection == 'past':  # Using elif so people could extend without this breaking
                for partial_line in line.matched_debit_ids:
                    if partial_line.create_date[:10] <= self.date_from:
                        line_amount += partial_line.amount_currency if foreign else partial_line.amount
                for partial_line in line.matched_credit_ids:
                    if partial_line.create_date[:10] <= self.date_from:
                        line_amount -= partial_line.amount_currency if foreign else partial_line.amount
                    # if foreign else partial_line.amount
            future_past[dict_key_id] += line_amount

        # Use one query per period and store results in history (a list variable)
        # Each history will contain: history[1] = {'<partner_id>': <partner_debit-credit>}
        history = []
        for i in range(5):
            if reconciled_after_date:
                args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            else:
                args_list = (tuple(move_state), tuple(account_type), tuple(partner_ids),)
            dates_query = '(COALESCE(l.date_maturity,l.date)'
            if form[str(i)]['start'] and form[str(i)]['stop']:
                dates_query += ' BETWEEN %s AND %s)'
                args_list += (form[str(i)]['start'], form[str(i)]['stop'])
            elif form[str(i)]['start']:
                dates_query += ' >= %s)'
                args_list += (form[str(i)]['start'],)
            else:
                dates_query += ' <= %s)'
                args_list += (form[str(i)]['stop'],)
            args_list += (date_from, user_company)

            query = '''SELECT l.partner_id, l.id AS line_id,l.move_id,'INV_'||a.id::text AS inv_id\
                        FROM account_move_line AS l
                        left join account_account on l.account_id = account_account.id
                        left join account_move am on l.move_id = am.id
                        left join account_invoice a on a.move_id = l.move_id
                        left join account_payment payment on payment.id = l.payment_id and payment.payment_via in ('normal','deposit','adv_payment')
                        WHERE
                            (am.state IN %s)
                            AND (account_account.internal_type IN %s)
                            AND (l.partner_id IN %s)
                            AND ''' + dates_query + '''
                            ''' + currency_condition + '''
                        AND ''' + line_date_condition + '''
                        AND l.company_id = %s
                        GROUP BY l.partner_id,l.id,l.move_id,a.id,payment.id
                        '''
            cr.execute(query, args_list)
            partners_partial = cr.fetchall()
            partners_amount = dict((i[0], 0) for i in partners_partial)
            aml_ids = partners_partial and [x[1] for x in partners_partial] or []
            for line in self.env['account.move.line'].browse(aml_ids):
                dict_key_id = line.partner_id.id

                if dict_key_id not in partners_amount:
                    partners_amount[dict_key_id] = 0.0
                line_amount = foreign and line.amount_currency or line.balance
                if not foreign and line.balance == 0:
                    continue
                if foreign and line.amount_currency == 0:
                    continue
                if self.direction_selection == 'future':
                    for partial_line in line.matched_debit_ids:
                        if partial_line.create_date[:10] >= self.date_from:
                            line_amount += partial_line.amount_currency if foreign else partial_line.amount
                    for partial_line in line.matched_credit_ids:
                        if partial_line.create_date[:10] >= self.date_from:
                            line_amount -= partial_line.amount_currency if foreign else partial_line.amount
                elif self.direction_selection == 'past':  # Using elif so people could extend without this breaking
                    for partial_line in line.matched_debit_ids:
                        if partial_line.create_date[:10] <= self.date_from:
                            line_amount += partial_line.amount_currency if foreign else partial_line.amount
                    for partial_line in line.matched_credit_ids:
                        if partial_line.create_date[:10] <= self.date_from:
                            line_amount -= partial_line.amount_currency if foreign else partial_line.amount
                partners_amount[dict_key_id] += line_amount

            # Note here merge two dictionary and then append (for invoice and payment)
            # to have only FIVE dictionary in list
            history.append(partners_amount)

        already_prceed_ids = []
        for partner in partners:
            if partner['id'] not in already_prceed_ids:
                already_prceed_ids.append(partner['id'])
                at_least_one_amount = False
                values = {}

                # #  If choise selection is in the future
                if self.direction_selection == 'future':
                    # Query here is replaced by one query which gets the all the partners their 'before' value
                    before = False
                    if future_past.has_key(partner['id']):
                        before = [future_past[partner['id']]]
                    self.total_account[6] = self.total_account[6] + (before and before[0] or 0.0)
                    values['direction'] = before and before[0] or 0.0
                elif self.direction_selection == 'past':  # Changed this so people could in the future create new direction_selections
                    # Query here is replaced by one query which gets the all the partners their 'after' value
                    after = False
                    if future_past.has_key(partner['id']):  # Making sure this partner actually was found by the query
                        after = [future_past[partner['id']]]

                    self.total_account[6] = self.total_account[6] + (after and after[0] or 0.0)
                    values['direction'] = after and after[0] or 0.0

                if not float_is_zero(values['direction'], precision_rounding=self.env.user.company_id.currency_id.rounding):
                    at_least_one_amount = True

                for i in range(5):
                    during = False
                    if history[i].has_key(partner['id']):
                        during = [history[i][partner['id']]]
                    # Adding counter
                    self.total_account[(i)] = self.total_account[(i)] + (during and during[0] or 0)
                    values[str(i)] = during and during[0] or 0.0
                    if not float_is_zero(values[str(i)], precision_rounding=self.env.user.company_id.currency_id.rounding):
                        at_least_one_amount = True
                values['total'] = sum([values['direction']] + [values[str(i)] for i in range(5)])
                # # Add for total
                self.total_account[(i + 1)] += values['total']
                values['name'] = partner['name']
                payment_term = False
                if partner['payment_term_id']:
                    payment_term = self.env['account.payment.term'].browse(partner['payment_term_id']).name
                values['payment_term'] = payment_term
                # values['date'] = partner['date']
                # values['ref'] = partner['ref']
                # values['move_ref'] = partner['move_ref']
                # values['actual_invoice_date'] = partner['actual_invoice_date']
                # values['code'] = partner['code']
                values['currency_name'] = partner.get('currency_name') or ''
                values['partner_id'] = partner['id']
                # values['payment_via'] = partner['payment_via']

                if at_least_one_amount:
                    if self._context and self._context.get('statement_end_date') and self._context.get('is_partner_balance'):
                        if partner['date']:
                            line_date = datetime.strptime(partner['date'], DEFAULT_SERVER_DATE_FORMAT)
                            statement_end_date = datetime.strptime(self._context['statement_end_date'], DEFAULT_SERVER_DATE_FORMAT)
                            if line_date < statement_end_date:
                                res.append(values)
                    else:
                        res.append(values)
        total = 0.0
        totals = {}
        new_dict_data = []
        for r in res:
            total += float(r['total'] or 0.0)
            for i in range(5) + ['direction']:
                totals.setdefault(str(i), 0.0)
                totals[str(i)] += float(r[str(i)] or 0.0)
        for data in res:
            data_dict = self._prepare_total_dict_data(data)
            new_dict_data.append(data_dict)
        return new_dict_data

    @api.multi
    def print_xls(self, data):
        self.ensure_one()
        self.total_account = []
        target_move = data['form'].get('target_move', 'all')
        date_from = data['form'].get('date_from', time.strftime('%Y-%m-%d'))

        if data['form']['result_selection'] == 'customer':
            account_type = ['receivable']
        elif data['form']['result_selection'] == 'supplier':
            account_type = ['payable']
        else:
            account_type = ['payable', 'receivable']

        #without_partner_movelines = self._get_move_lines_with_out_partner(data['form'], account_type, date_from, target_move)
        #tot_list = self.total_account
        # partner_movelines = self._get_partner_move_lines(data['form'], account_type, date_from, target_move)
#         print "partner_movelines==",partner_movelines
#         print "self.total_account ", self.total_account
#         for i in range(7):
#             self.total_account[i] += tot_list[i]
#        movelines = partner_movelines #+ without_partner_movelines

        if data['form']['report_type'] == 'detail':
            partner_movelines = self._get_partner_move_lines(data['form'], account_type, date_from, target_move)
            if data['form'].get('page_split'):
                return self.print_multi_tab(data, partner_movelines)
            else:
                return self.print_single_tab(data, partner_movelines)
        else:
            partner_movelines = self._get_partner_summary_move_lines(data['form'], account_type, date_from, target_move)
            return self.print_summary_report(data, partner_movelines)

    def print_summary_report(self, data, partner_movelines):
        fl = StringIO()
        workbook = xlsxwriter.Workbook(fl, {'in_memory': True})
        worksheet = workbook.add_worksheet('Customer-Aging')
        style = workbook.add_format({'font_size': 10})

        label_style = workbook.add_format({'bold':  True, 'font_size': 10})

        style_right_align = workbook.add_format()
        style_right_align.set_align('right')

        style_bold_right_align = workbook.add_format({'bold':  True, 'font_size': 10})
        style_bold_right_align.set_align('right')

        company_name = ''
        user = self.env['res.users'].browse(self._context.get('uid'))
        if user:
            company_name = user.company_id.name

        # if data['form']['result_selection'] == 'customer':
        #     worksheet.merge_range('A1:E1', company_name + ' : ' + 'Customer Aging Report', label_style)
        # elif data['form']['result_selection'] == 'supplier':
        #     worksheet.merge_range('A1:E1', company_name + ' : ' + 'Supplier Aging Report - Detail', label_style)
        # else:
        worksheet.merge_range('A1:E1', company_name + ' : ' + 'Partner Aging Report - Summary', label_style)
        worksheet.merge_range('G1:J1', 'Report Print Date' + ' : ' + fields.Datetime.now(), label_style)

#         worksheet.write(10,1,'Journals :',label_style)
#         worksheet.merge_range('B11:K12',print_journal)

        worksheet.write(2, 0, 'Start Date:', label_style)
        worksheet.write(3, 0, data['form'].get('date_from', time.strftime('%Y-%m-%d')))

        worksheet.write(2, 2, 'Period Length (days):', label_style)
        worksheet.write(3, 2, data['form']['period_length'])

        worksheet.write(2, 4, 'Partner\'s:', label_style)
        worksheet.write(3, 4, data['form']['result_selection'])

        worksheet.write(2, 6, 'Analysis Direction :', label_style)
        worksheet.write(3, 6, data['form']['direction_selection'])

        worksheet.write(2, 8, 'Target Moves :', label_style)
        worksheet.write(3, 8, data['form'].get('target_move', 'all'))

        def print_header(col, label_style):
            worksheet.write(col, 0, 'Partners', label_style)
            worksheet.write(col, 1, 'Payment term', label_style)

            if data['form']['direction_selection'] == 'future':
                worksheet.write(col, 2, 'Due', label_style)
            else:
                worksheet.write(col, 2, 'Not Due', label_style)

            worksheet.write(col, 3, data['form']['4']['name'], label_style)
            worksheet.write(col, 4, data['form']['3']['name'], label_style)
            worksheet.write(col, 5, data['form']['2']['name'], label_style)
            worksheet.write(col, 6, data['form']['1']['name'], label_style)
            worksheet.write(col, 7, data['form']['0']['name'], label_style)
            worksheet.write(col, 8, 'Total', label_style)
            worksheet.write(col, 9, 'Currency', label_style)

        def print_total_line(col, label, label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency_name):
            worksheet.write(col, 0, label, label_style)
            worksheet.write(col, 1, '', label_style)
            worksheet.write(col, 2, float(round(direction_total, 2)), label_style)
            worksheet.write(col, 3, float(round(four_total, 2)), label_style)
            worksheet.write(col, 4, float(round(three_total, 2)), label_style)
            worksheet.write(col, 5, float(round(two_total, 2)), label_style)
            worksheet.write(col, 6, float(round(one_total, 2)), label_style)
            worksheet.write(col, 7, float(round(zero_total, 2)), label_style)
            worksheet.write(col, 8, float(round(total_total, 2)), label_style)
            worksheet.write(col, 9, currency_name, label_style)

        def print_main_total_line(col, label, label_style, base_currency_name):
            worksheet.write(col, 0, label, label_style)
            worksheet.write(col, 1, '', label_style)
            worksheet.write(col, 2, float(round(self.total_account[6], 2)), label_style)
            worksheet.write(col, 3, float(round(self.total_account[4], 2)), label_style)
            worksheet.write(col, 4, float(round(self.total_account[3], 2)), label_style)
            worksheet.write(col, 5, float(round(self.total_account[2], 2)), label_style)
            worksheet.write(col, 6, float(round(self.total_account[1], 2)), label_style)
            worksheet.write(col, 7, float(round(self.total_account[0], 2)), label_style)
            worksheet.write(col, 8, float(round(self.total_account[5], 2)), label_style)
            worksheet.write(col, 9, base_currency_name, label_style)

        print_header(5, label_style)
        if data['form']['currency_selection'] == 'base_currency':
            base_currency_name = partner_movelines and partner_movelines[0].get('currency_name') or ''
            print_main_total_line(7, "Account Total", label_style, base_currency_name)
        row = 0
        colum = 8
        sheet_count = 1
        max_limit = 1048576 - colum

        currency = False
        direction_total = 0.0
        four_total = 0.0
        three_total = 0.0
        two_total = 0.0
        one_total = 0.0
        zero_total = 0.0
        total_total = 0.0
        total_line = len(partner_movelines)
        i = 0
        for partner in sorted(partner_movelines, key=itemgetter('name', 'currency_name')):
            i += 1
            if currency and currency == partner.get('currency_name'):
                direction_total += partner.get('direction', 0)
                four_total += partner.get('4', 0)
                three_total += partner.get('3', 0)
                two_total += partner.get('2', 0)
                one_total += partner.get('1', 0)
                zero_total += partner.get('0', 0)
                total_total += partner.get('total', 0)
            elif (currency and currency != partner.get('currency_name')) or (not currency):
                if currency and data['form']['currency_selection'] == 'foreign_currency':
                    print_total_line(colum, 'Total', label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency)
                    colum += 2
                direction_total = partner.get('direction', 0)
                four_total = partner.get('4', 0)
                three_total = partner.get('3', 0)
                two_total = partner.get('2', 0)
                one_total = partner.get('1', 0)
                zero_total = partner.get('0', 0)
                total_total = partner.get('total', 0)

            currency = partner.get('currency_name')
            # this code is to change the sheet when row limit over of xlswriter
            if colum > max_limit:
                max_limit += max_limit
                colum = 1
                worksheet = workbook.add_worksheet('customer-aging-'+str(sheet_count))
                sheet_count += 1
                print_header(0, label_style)

            worksheet.write(colum, row, partner['name'], style)
            row += 1

            worksheet.write(colum, row, partner['payment_term'] or '', style)
            row += 1

            worksheet.write(colum, row, float(round(partner.get('direction', 0), 2)), style)
            row += 1

            worksheet.write(colum, row, float(round(partner.get('4', 0), 2)), style)
            row += 1

            worksheet.write(colum, row, float(round(partner.get('3', 0), 2)), style)
            row += 1

            worksheet.write(colum, row, float(round(partner.get('2', 0), 2)), style)
            row += 1

            worksheet.write(colum, row, float(round(partner.get('1', 0), 2)), style)
            row += 1

            worksheet.write(colum, row, float(round(partner.get('0', 0), 2)), style)
            row += 1

            worksheet.write(colum, row, float(round(partner.get('total', 0), 2)), style)
            row += 1

            worksheet.write(colum, row, partner.get('currency_name'), style)
            row += 1

            colum += 1
            row = 0

            if total_line == i and data['form']['currency_selection'] == 'foreign_currency':
                print_total_line(colum, 'Total', label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency)

        workbook.close()
        fl.seek(0)
        buf = base64.encodestring(fl.read())
        filename = "partner_aging"
        self.write({'file': buf, 'name': filename})
        # print "return=== file"
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=account.aged.trial.balance.new&field=file&id=%s&filename=%s.xls' % (self.id, filename),
            'target': 'self',
            }

    def print_single_tab(self, data, partner_movelines):
        fl = StringIO()
        workbook = xlsxwriter.Workbook(fl, {'in_memory': True})
        worksheet = workbook.add_worksheet('Customer-Aging')
        style = workbook.add_format({'font_size': 10})
        
        label_style = workbook.add_format({'bold':  True, 'font_size': 10})
        
        style_right_align = workbook.add_format()
        style_right_align.set_align('right')
        
        style_bold_right_align = workbook.add_format({'bold':  True, 'font_size': 10})
        style_bold_right_align.set_align('right')
        
        company_name = ''
        user = self.env['res.users'].browse(self._context.get('uid'))
        if user:
            company_name = user.company_id.name
            
        
        # if data['form']['result_selection'] == 'customer':
        #     worksheet.merge_range('A1:E1', company_name + ' : ' + 'Customer Aging Report',label_style)
        # elif data['form']['result_selection'] == 'supplier':
        #     worksheet.merge_range('A1:E1', company_name + ' : ' + 'Supplier Aging Report',label_style)
        # else:
        worksheet.merge_range('A1:E1', company_name + ' : ' + 'Partner Aging Report - Detail', label_style)
        worksheet.merge_range('G1:J1', 'Report Print Date' + ' : ' + fields.Datetime.now(), label_style)


        worksheet.write(2,0,'Start Date:',label_style)
        worksheet.write(3,0,data['form'].get('date_from', time.strftime('%Y-%m-%d')))
        
        
        worksheet.write(2,2,'Period Length (days):',label_style)
        worksheet.write(3,2,data['form']['period_length'])
        
        worksheet.write(2,4,'Partner\'s:',label_style)
        worksheet.write(3,4,data['form']['result_selection'])
        
        worksheet.write(2,6,'Analysis Direction :',label_style)
        worksheet.write(3,6,data['form']['direction_selection'])
        
        worksheet.write(2,8,'Target Moves :',label_style)
        worksheet.write(3,8,data['form'].get('target_move', 'all'))
        
        
        def print_header(col,label_style):
            worksheet.write(col,0,'Code',label_style)
            worksheet.write(col,1,'Date',label_style)
            worksheet.write(col,2,'Actual Bill Date',label_style)
            worksheet.write(col,3,'Doc Number',label_style)
            worksheet.write(col,4,'Inv No / Ref',label_style)
            worksheet.write(col,5,'Payment Type',label_style)
            worksheet.write(col,6, 'Memo',label_style)
            worksheet.write(col,7,'Partners',label_style)
            worksheet.write(col,8,'Payment term',label_style)
            
            if data['form']['direction_selection'] == 'future':
                worksheet.write(col,9,'Due',label_style)
            else:
                worksheet.write(col,9,'Not Due',label_style)
                
            worksheet.write(col,10,data['form']['4']['name'],label_style)
            worksheet.write(col,11,data['form']['3']['name'],label_style)
            worksheet.write(col,12,data['form']['2']['name'],label_style)
            worksheet.write(col,13,data['form']['1']['name'],label_style)
            worksheet.write(col,14,data['form']['0']['name'],label_style)
            worksheet.write(col,15,'Total',label_style)
            worksheet.write(col,16,'Currency',label_style)
            
        def print_total_line(col, label, label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency_name):
            worksheet.write(col,0,label,label_style)
            worksheet.write(col,9, float(round( direction_total ,2)) ,label_style)
            worksheet.write(col,10, float(round( four_total ,2)) ,label_style)
            worksheet.write(col,11, float(round( three_total ,2)) ,label_style)
            worksheet.write(col,12, float(round( two_total ,2)) ,label_style)
            worksheet.write(col,13, float(round( one_total ,2)) ,label_style)
            worksheet.write(col,14,float(round( zero_total ,2)) ,label_style)
            worksheet.write(col,15,float(round( total_total ,2)) ,label_style)
            worksheet.write(col,16, currency_name ,label_style)
        
        def print_main_total_line(col, label, label_style, base_currency_name):
            worksheet.write(col,0,label,label_style)
            worksheet.write(col,9, float(round( self.total_account[6] ,2)) ,label_style)
            worksheet.write(col,10, float(round( self.total_account[4] ,2)) ,label_style)
            worksheet.write(col,11, float(round( self.total_account[3] ,2)) ,label_style)
            worksheet.write(col,12, float(round( self.total_account[2] ,2)) ,label_style)
            worksheet.write(col,13, float(round( self.total_account[1] ,2)) ,label_style)
            worksheet.write(col,14,float(round( self.total_account[0] ,2)) ,label_style)
            worksheet.write(col,15,float(round( self.total_account[5] ,2)) ,label_style)
            worksheet.write(col,16,base_currency_name ,label_style)
        
        print_header(5, label_style)
        
        if data['form']['currency_selection'] == 'base_currency':
            base_currency_name = partner_movelines and partner_movelines[0].get('currency_name') or ''
            print_main_total_line(8, "Account Total", label_style, base_currency_name)
        
        
        row = 0
        colum = 8
        sheet_count = 1
        max_limit = 1048576 - colum

        currency = False
        direction_total = 0.0
        four_total = 0.0
        three_total = 0.0
        two_total = 0.0
        one_total = 0.0
        zero_total = 0.0
        total_total = 0.0
        total_line = len(partner_movelines)
        i = 0
        for partner in sorted(partner_movelines, key=itemgetter('name','currency_name','date')):
            i += 1
            if currency and currency == partner.get('currency_name'):
                direction_total += partner.get('direction',0)
                four_total += partner.get('4',0)
                three_total += partner.get('3',0)
                two_total += partner.get('2',0)
                one_total += partner.get('1',0)
                zero_total += partner.get('0',0)
                total_total += partner.get('total',0)
            elif (currency and currency != partner.get('currency_name')) or (not currency):
                if currency and data['form']['currency_selection'] == 'foreign_currency':
                    print_total_line(colum, 'Total', label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency)
                    colum += 2
                direction_total = partner.get('direction',0)
                four_total = partner.get('4',0)
                three_total = partner.get('3',0)
                two_total = partner.get('2',0)
                one_total = partner.get('1',0)
                zero_total = partner.get('0',0)
                total_total = partner.get('total',0)
                
            currency = partner.get('currency_name')
            # this code is to change the sheet when row limit over of xlswriter
            if colum > max_limit:
                max_limit += max_limit
                colum = 1
                worksheet = workbook.add_worksheet('customer-aging-'+str(sheet_count))
                sheet_count += 1
                print_header(0,label_style)
            worksheet.write(colum,row,partner['code'],style)
            row += 1
            
            worksheet.write(colum,row,partner['date'],style)
            row += 1
            
            worksheet.write(colum,row,partner['actual_invoice_date'],style)
            row += 1
            
            worksheet.write(colum,row,partner['ref'],style)
            row += 1
            
            worksheet.write(colum,row,partner['move_ref'],style)
            row += 1
            
            worksheet.write(colum,row,partner.get('payment_via') and partner['payment_via'].title(),style)
            row += 1

            worksheet.write(colum, row, partner['memo'] or '', style)
            row += 1
            
            worksheet.write(colum,row,partner['name'],style)
            row += 1
            
            worksheet.write(colum,row,partner['payment_term'] or '',style)
            row += 1
            
            worksheet.write(colum,row, float(round( partner.get('direction',0),2)) ,style)
            row += 1
            
            worksheet.write(colum,row, float(round( partner.get('4',0),2)) ,style)
            row += 1
            
            worksheet.write(colum,row, float(round( partner.get('3',0),2)) ,style)
            row += 1
            
            worksheet.write(colum,row, float(round( partner.get('2',0),2)) ,style)
            row += 1
            
            worksheet.write(colum,row, float(round( partner.get('1',0),2)) ,style)
            row += 1
            
            worksheet.write(colum,row, float(round( partner.get('0',0),2)) ,style)
            row += 1
            
            worksheet.write(colum,row, float(round( partner.get('total',0),2)) ,style)
            row += 1
            
            worksheet.write(colum,row, partner.get('currency_name') ,style)
            row += 1
            
            colum += 1
            row = 0
            
            if total_line == i and data['form']['currency_selection'] == 'foreign_currency':
                print_total_line(colum, 'Total', label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency)
                
        workbook.close()
        fl.seek(0)
        buf = base64.encodestring(fl.read())
        filename = "partner_aging"
        self.write({'file': buf,'name': filename})
        #print "return=== file"
        return { 
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=account.aged.trial.balance.new&field=file&id=%s&filename=%s.xls'%(self.id, filename),
            'target': 'self',
            }

    def print_multi_tab(self, data, partner_movelines):
        fl = StringIO()
        workbook = xlsxwriter.Workbook(fl, {'in_memory': True})
        style = workbook.add_format({'font_size': 10})

        label_style = workbook.add_format({'bold':  True, 'font_size': 10})

        style_right_align = workbook.add_format()
        style_right_align.set_align('right')

        style_bold_right_align = workbook.add_format({'bold':  True, 'font_size': 10})
        style_bold_right_align.set_align('right')

        company_name = ''
        user = self.env['res.users'].browse(self._context.get('uid'))
        if user:
            company_name = user.company_id.name

        def print_header(col, label_style):
            worksheet.write(col,0,'Code',label_style)
            worksheet.write(col,1,'Date',label_style)
            worksheet.write(col,2,'Actual Bill Date',label_style)
            worksheet.write(col,3,'Doc Number',label_style)
            worksheet.write(col,4,'Inv No / Ref',label_style)
            worksheet.write(col,5,'Payment Type',label_style)
            worksheet.write(col,6,'Memo',label_style)
            worksheet.write(col,7,'Partners',label_style)
            worksheet.write(col,8,'Payment term',label_style)
            
            if data['form']['direction_selection'] == 'future':
                worksheet.write(col,9,'Due',label_style)
            else:
                worksheet.write(col,9,'Not Due',label_style)
                
            worksheet.write(col,10,data['form']['4']['name'],label_style)
            worksheet.write(col,11,data['form']['3']['name'],label_style)
            worksheet.write(col,12,data['form']['2']['name'],label_style)
            worksheet.write(col,13,data['form']['1']['name'],label_style)
            worksheet.write(col,14,data['form']['0']['name'],label_style)
            worksheet.write(col,15,'Total',label_style)
            worksheet.write(col,16,'Currency',label_style)
            
        def print_sub_total(col, partner, label_style, base_currency_name,partner_age_total):
            worksheet.write(col,0,'Sub Total:',label_style)
            worksheet.write(col,9, float(round( partner['dir'] ,2)) ,label_style)
            worksheet.write(col,10, float(round( partner['four'] ,2)) ,label_style)
            worksheet.write(col,11, float(round( partner['three'] ,2)) ,label_style)
            worksheet.write(col,12, float(round( partner['two'] ,2)) ,label_style)
            worksheet.write(col,13, float(round( partner['one'] ,2)) ,label_style)
            worksheet.write(col,14,float(round( partner['zero'] ,2)) ,label_style)
            worksheet.write(col,15,float(round( partner['final_total'] ,2)) ,label_style)
            worksheet.write(col,16,base_currency_name ,label_style)
            
            currency_obj = self.env['res.currency'].search([('name','=',base_currency_name)], limit=1)
            partner_age_total[partner['partner_id']].update({currency_obj:
                                                            {'not_due':['Not Due', partner['dir']],
                                                            4: [data['form']['4']['name'], partner['four']],
                                                            3: [data['form']['3']['name'], partner['three']],
                                                            2: [data['form']['2']['name'], partner['two']],
                                                            1: [data['form']['1']['name'], partner['one']],
                                                            0: [data['form']['0']['name'], partner['zero']],
                                                            }
                                                        })
            
            
        def print_total_line(col, label, label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency_name, partner, partner_age_total):
            worksheet.write(col,0,label,label_style)
            worksheet.write(col,9, float(round( direction_total ,2)) ,label_style)
            worksheet.write(col,10, float(round( four_total ,2)) ,label_style)
            worksheet.write(col,11, float(round( three_total ,2)) ,label_style)
            worksheet.write(col,12, float(round( two_total ,2)) ,label_style)
            worksheet.write(col,13, float(round( one_total ,2)) ,label_style)
            worksheet.write(col,14,float(round( zero_total ,2)) ,label_style)
            worksheet.write(col,15,float(round( total_total ,2)) ,label_style)
            worksheet.write(col,16, currency_name ,label_style)
            
            currency_obj = self.env['res.currency'].search([('name','=',currency_name)], limit=1)
            partner_age_total[partner['partner_id']].update({currency_obj:
                                                            {'not_due': ['Not Due', direction_total],
                                                            4: [data['form']['4']['name'], four_total],
                                                            3: [data['form']['3']['name'], three_total],
                                                            2: [data['form']['2']['name'], two_total],
                                                            1: [data['form']['1']['name'], one_total],
                                                            0: [data['form']['0']['name'], zero_total],
                                                            }
                                                        })
        
        sheet_name_lst = []
        
        row = 0
        partner_age_total = {}
        for partner_list in partner_movelines:
            partner_age_total[partner_list['partner_id']] = {}
            sheet_name = partner_list['info'][0]['name']
            for ch in [ '[',']','*','?',':','/','\\' ]:
                if ch in sheet_name:
                    sheet_name=sheet_name.replace(ch, ' ')
            if sheet_name in sheet_name_lst:
                sheet_name = sheet_name + '.'
            sheet_name_lst.append(sheet_name)
            
            if len(sheet_name) > 31:
                worksheet = workbook.add_worksheet(sheet_name[:31])
            else:
                worksheet = workbook.add_worksheet(sheet_name)
            
            # if data['form']['result_selection'] == 'customer':
            #     worksheet.merge_range('A1:D1','Customer Aging Report',label_style)
            # elif data['form']['result_selection'] == 'supplier':
            #     worksheet.merge_range('A1:D1','Supplier Aging Report',label_style)
            # else:
            worksheet.merge_range('A1:D1', company_name + ' : ' + 'Partner Aging Report - Detail', label_style)
            worksheet.merge_range('G1:J1', 'Report Print Date' + ' : ' + fields.Datetime.now(), label_style)
                
            
    #         worksheet.write(10,1,'Journals :',label_style)
    #         worksheet.merge_range('B11:K12',print_journal)
            
            
            
            worksheet.write(2,0,'Start Date:',label_style)
            worksheet.write(3,0,data['form'].get('date_from', time.strftime('%Y-%m-%d')))
            
            
            worksheet.write(2,2,'Period Length (days):',label_style)
            worksheet.write(3,2,data['form']['period_length'])
            
            worksheet.write(2,4,'Partner\'s:',label_style)
            worksheet.write(3,4,data['form']['result_selection'])
            
            worksheet.write(2,6,'Analysis Direction :',label_style)
            worksheet.write(3,6,data['form']['direction_selection'])
            
            worksheet.write(2,8,'Target Moves :',label_style)
            worksheet.write(3,8,data['form'].get('target_move', 'all'))
        
            # it will print header
            print_header(5,label_style)
            
            colum = 7
            
            currency = False
            direction_total = 0.0
            four_total = 0.0
            three_total = 0.0
            two_total = 0.0
            one_total = 0.0
            zero_total = 0.0
            total_total = 0.0
            total_line = len(partner_list['info'])
            i = 0
            
            for partner in sorted(partner_list['info'], key=itemgetter('name','currency_name','date')):
                
                i += 1
                if currency and currency == partner.get('currency_name'):
                    direction_total += partner.get('direction',0)
                    four_total += partner.get('4',0)
                    three_total += partner.get('3',0)
                    two_total += partner.get('2',0)
                    one_total += partner.get('1',0)
                    zero_total += partner.get('0',0)
                    total_total += partner.get('total',0)
                elif (currency and currency != partner.get('currency_name')) or (not currency):
                    if currency and data['form']['currency_selection'] == 'foreign_currency':
                        print_total_line(colum, 'Total', label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency, partner_list, partner_age_total)
                        colum += 2
                    direction_total = partner.get('direction',0)
                    four_total = partner.get('4',0)
                    three_total = partner.get('3',0)
                    two_total = partner.get('2',0)
                    one_total = partner.get('1',0)
                    zero_total = partner.get('0',0)
                    total_total = partner.get('total',0)
                    
                currency = partner.get('currency_name')
                
                worksheet.write(colum,row,partner['code'],style)
                row += 1
                
                worksheet.write(colum,row,partner['date'],style)
                row += 1
                
                worksheet.write(colum,row,partner['actual_invoice_date'],style)
                row += 1
                
                worksheet.write(colum,row,partner['ref'],style)
                row += 1
                
                worksheet.write(colum,row,partner['move_ref'],style)
                row += 1
                
                worksheet.write(colum,row,partner.get('payment_via') and partner['payment_via'].title(),style)
                row += 1

                worksheet.write(colum,row,partner.get('memo') or '',style)
                row += 1
                
                worksheet.write(colum,row,partner['name'],style)
                row += 1
                
                worksheet.write(colum,row,partner['payment_term'] or '',style)
                row += 1
                
                worksheet.write(colum,row, float(round( partner.get('direction',0),2)) ,style)
                row += 1
                
                worksheet.write(colum,row, float(round( partner.get('4',0),2)) ,style)
                row += 1
                
                worksheet.write(colum,row, float(round( partner.get('3',0),2)) ,style)
                row += 1
                
                worksheet.write(colum,row, float(round( partner.get('2',0),2)) ,style)
                row += 1
                
                worksheet.write(colum,row, float(round( partner.get('1',0),2)) ,style)
                row += 1
                
                worksheet.write(colum,row, float(round( partner.get('0',0),2)) ,style)
                row += 1
                
                worksheet.write(colum,row, float(round( partner.get('total',0),2)) ,style)
                row += 1
                
                worksheet.write(colum,row, partner.get('currency_name') ,style)
                row += 1
                
                colum += 1
                row = 0
                
                if total_line == i and data['form']['currency_selection'] == 'foreign_currency':
                    print_total_line(colum, 'Total', label_style, direction_total, four_total, three_total, two_total, one_total, zero_total, total_total, currency, partner_list, partner_age_total)
            
            if total_line == i and data['form']['currency_selection'] == 'base_currency':
                base_currency_name = partner_list['info'] and partner_list['info'][0].get('currency_name') or ''
                print_sub_total(colum, partner_list, label_style, base_currency_name,partner_age_total)

        if self._context.get('is_partner_balance'):
            return partner_age_total
        workbook.close()
        fl.seek(0)
        buf = base64.encodestring(fl.read())
        filename = "partner_aging"
        self.write({'file': buf,'name': filename})
        
        return { 
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=account.aged.trial.balance.new&field=file&id=%s&filename=%s.xls'%(self.id, filename),
            'target': 'self',
            }
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
