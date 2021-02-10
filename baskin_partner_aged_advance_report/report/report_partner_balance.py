# -*- coding: utf-8 -*-

import time
from openerp import api, fields, models
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT


class ReportOverdue(models.AbstractModel):
    _name = 'report.baskin_partner_aged_advance_report.report_partner_bal'

    def _get_initial_balance(self, partner_ids):
        res = dict(map(lambda x:(x,{}), partner_ids))
        docs = self.env['partner.statement.wizard'].browse(self.ids)
        date_clouse = ""
        if docs.date_from and docs.date_end:
            date_clouse = """AND (l.date < '%s')"""%(docs.date_from)
            
        currency_clause = "AND l.currency_id is null"
        if docs.currency_selection == 'foreign_currency':
            currency_clause = 'AND l.currency_id is not null'
            
        target_move_clouse = ""
        if docs.target_move and docs.target_move == 'posted':
            target_move_clouse = "AND m.state = 'posted'"
            
        query = """SELECT 
                    l.partner_id, 
                    l.currency_id, 
                    sum(l.amount_currency) as balance_currency, 
                    sum(l.debit - l.credit) as balance
            
                FROM account_move_line l 
                JOIN account_account_type at ON (l.user_type_id = at.id) 
                JOIN account_move m ON (l.move_id = m.id) 
                WHERE l.partner_id IN %s AND at.type IN ('receivable', 'payable') 
                    {date_clouse}
                    {currency_clause}
                    {target_move_clouse}
                    
                GROUP BY l.partner_id, l.currency_id
            """.format(date_clouse=date_clouse,
                       currency_clause=currency_clause,
                       target_move_clouse=target_move_clouse,
                       )
        
        params = ( (tuple(partner_ids),) )
           
        self.env.cr.execute(query, params)
        for row in self.env.cr.dictfetchall():
            print "row--------------",row
            partner_id = row.pop('partner_id')
            currency_id = row.pop('currency_id')
            if not currency_id:
                currency_id = 'base'
            res[partner_id][currency_id] = []
            res[partner_id][currency_id].append(row)
            
        print "initial balance result",res
        return res
        
    
    def _get_account_move_lines(self, partner_ids):
        docs = self.env['partner.statement.wizard'].browse(self.ids)
        
        initital_balance = self._get_initial_balance(partner_ids)
        
        res = dict(map(lambda x:(x,[]), partner_ids))
        
        currency_clause = "AND l.currency_id is null"
        if docs.currency_selection == 'foreign_currency':
            currency_clause = 'AND l.currency_id is not null'
        
        date_clouse = ""
        if docs.date_from and docs.date_end:
            date_clouse = """AND ((l.date >= '%s') and
                                  (l.date <= '%s') )"""%(docs.date_from,docs.date_end)
        
                                     
        target_move_clouse = ""
        if docs.target_move and docs.target_move == 'posted':
            target_move_clouse = "AND m.state = 'posted'"
        
        
        reconciliation_clause = ''
        if docs.report_type and docs.report_type == 'outstanding':
            reconciliation_clause = 'AND l.reconciled IS FALSE'
        
        query = """SELECT 
                        l.id as line_id, 
                        m.name AS move_id, 
                        l.date, 
                        l.name, 
                        l.ref, 
                        l.date_maturity,
                        a.actual_invoice_date,
                        a.name as invoice_ref,
                        a.reference as reference, 
                        l.partner_id, 
                        l.blocked, 
                        l.amount_currency, 
                        l.currency_id, 
            CASE WHEN at.type = 'receivable' 
                THEN SUM(l.debit) 
                ELSE SUM(l.credit * -1) 
            END AS debit, 
            CASE WHEN at.type = 'receivable' 
                THEN SUM(l.credit) 
                ELSE SUM(l.debit * -1) 
            END AS credit, 
            CASE WHEN l.date_maturity < %s 
                THEN SUM(l.debit - l.credit) 
                ELSE 0 
            END AS mat 
            FROM account_move_line l 
            JOIN account_account_type at ON (l.user_type_id = at.id) 
            JOIN account_move m ON (l.move_id = m.id)
            LEFT JOIN account_invoice as a ON (l.move_id = a.move_id) 
            WHERE l.partner_id IN %s AND at.type IN ('receivable', 'payable') 
            {date_clouse}
            {currency_clause}
            {target_move_clouse}
            {reconciliation_clause}
            GROUP BY l.id, 
                    l.date, 
                    l.name, 
                    l.ref, 
                    l.date_maturity, 
                    l.partner_id, 
                    at.type, 
                    l.blocked, 
                    l.amount_currency, 
                    l.currency_id, 
                    l.move_id, 
                    m.name,
                    a.actual_invoice_date,
                    a.name,
                    a.reference
            """.format(date_clouse=date_clouse,
                       currency_clause=currency_clause,
                       target_move_clouse=target_move_clouse,
                       reconciliation_clause=reconciliation_clause)
        
        params = ( (fields.date.today(), ) + (tuple(partner_ids),) )
           
        # print "query---",query,params
        self.env.cr.execute(query, params)
        for row in self.env.cr.dictfetchall():
            res[row.pop('partner_id')].append(row)
        
        if docs.report_type and docs.report_type == 'outstanding':
            for all_partner_line in res:
                for partner_line in res[all_partner_line]:
                    line = self.env['account.move.line'].browse([partner_line['line_id']])
                    for partial_line in line.matched_debit_ids:
                        if partial_line.create_date[:10] >= docs.date_from and partial_line.create_date[:10] <= docs.date_end:
                            partner_line['credit'] += partial_line.amount
                            partner_line['amount_currency'] += partial_line.amount_currency 
                    for partial_line in line.matched_credit_ids:
                        if partial_line.create_date[:10] >= docs.date_from and partial_line.create_date[:10] <= docs.date_end:
                            partner_line['debit'] -= partial_line.amount
                            partner_line['amount_currency'] -= partial_line.amount_currency
                            
        
        # here for last aging table we just use the same logic of the partner aging report 
        # (so create wizard record and call print method)
        # with one flag in context and handle this flag in aging report code.
        aging_date = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        age_new = self.env['account.aged.trial.balance.new'].create({
            'currency_selection':docs.currency_selection,
            'page_split' : True,
            'partner_ids': [(6,False,partner_ids)],
            'date_from' : aging_date,
            'target_move': 'posted'
            })
        result_aging = age_new.with_context(is_partner_balance=True,
                                            statement_end_date=docs.date_end).check_report()
        print "result_aging----",result_aging
        return res,initital_balance,result_aging

    @api.multi
    def render_html(self, data):
        docs = self.env['partner.statement.wizard'].browse(self.ids)
        totals = {}
        lines,initital_balance,result_aging = self._get_account_move_lines(docs.partner_ids.ids)
        lines_to_display = {}
        company_currency = self.env.user.company_id.currency_id
        for partner_id in docs.partner_ids.ids:
            lines_to_display[partner_id] = {}
            totals[partner_id] = {}
            for line_tmp in lines[partner_id]:
                line = line_tmp.copy()
                currency = line['currency_id'] and self.env['res.currency'].browse(line['currency_id']) or company_currency
                if currency not in lines_to_display[partner_id]:
                    lines_to_display[partner_id][currency] = []
                    totals[partner_id][currency] = dict((fn, 0.0) for fn in ['due', 'paid', 'mat', 'total'])
                if line['debit'] and line['currency_id']:
                    line['debit'] = line['amount_currency']
                if line['credit'] and line['currency_id']:
                    line['credit'] = line['amount_currency']
                if line['mat'] and line['currency_id']:
                    line['mat'] = line['amount_currency']
                lines_to_display[partner_id][currency].append(line)
                if not line['blocked']:
                    totals[partner_id][currency]['due'] += line['debit']
                    totals[partner_id][currency]['paid'] += line['credit']
                    totals[partner_id][currency]['mat'] += line['mat']
                    totals[partner_id][currency]['total'] += line['debit'] - line['credit']
        
        print "lines_to_display---",lines_to_display
        docargs = {
            'doc_ids': docs,
            'partner_ids': docs.partner_ids.ids,
            'result_aging':result_aging,
            'doc_model': 'res.partner',
            'docs': self.env['res.partner'].browse(docs.partner_ids.ids),
            'time': time,
            'Lines': lines_to_display,
            'initital_balance':initital_balance,
            'Totals': totals,
            'Date': fields.date.today(),
            'company': self.env.user.company_id
        }
        return self.env['report'].render('baskin_partner_aged_advance_report.report_partner_bal', values=docargs)
