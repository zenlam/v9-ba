# -*- coding: utf-8 -*-

from openerp import fields, models, api, tools, _
from openerp.tools import misc
from openerp.tools.misc import str2bool
import xlsxwriter
from cStringIO import StringIO
import tempfile
import base64
from datetime import datetime
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class AccountReportGeneralLedger(models.TransientModel):
    _inherit = "account.report.general.ledger"
    
    
    
    file = fields.Binary('Click On Download Link To Download Xls File', readonly=True)
    name = fields.Char(string='File Name', size=64)
    table_id = fields.Many2one('gl.archive.table', string="Table Name", required=False)
    
    def _get_account_move_entry(self, accounts, init_balance, sortby, display_account):
        """
        :param:
                accounts: the recordset of accounts
                init_balance: boolean value of initial_balance
                sortby: sorting by date or partner and journal
                display_account: type of account(receivable, payable and both)

        Returns a dictionary of accounts with following key and value {
                'code': account code,
                'name': account name,
                'debit': sum of total debit amount,
                'credit': sum of total credit amount,
                'balance': total balance,
                'amount_currency': sum of amount_currency,
                'move_lines': list of move line
        }
        """
        cr = self.env.cr
        MoveLine = self.env['account.move.line']
        move_lines = dict(map(lambda x: (x, []), accounts.ids))

        # Prepare initial sql query and Get the initial move lines
        if init_balance:
            init_tables, init_where_clause, init_where_params = MoveLine.with_context(date_from=self.env.context.get('date_from'), date_to=False, initial_bal=True)._query_get()
            init_wheres = [""]
            if init_where_clause.strip():
                init_wheres.append(init_where_clause.strip())
            init_filters = " AND ".join(init_wheres)
            filters = init_filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')
            sql = ("SELECT 0 AS lid, l.account_id AS account_id, '' AS ldate, '' AS lcode, NULL AS amount_currency, '' AS lref, 'Initial Balance' AS lname, COALESCE(SUM(l.debit),0.0) AS debit, COALESCE(SUM(l.credit),0.0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) as balance, '' AS lpartner_id,\
                '' AS move_name, '' AS mmove_id, '' AS currency_code,\
                NULL AS currency_id,\
                '' AS invoice_id, '' AS invoice_type, '' AS invoice_number,\
                '' AS partner_name\
                FROM account_move_line l\
                LEFT JOIN account_move m ON (l.move_id=m.id)\
                LEFT JOIN res_currency c ON (l.currency_id=c.id)\
                LEFT JOIN res_partner p ON (l.partner_id=p.id)\
                LEFT JOIN account_invoice i ON (m.id =i.move_id)\
                JOIN account_journal j ON (l.journal_id=j.id)\
                WHERE l.account_id IN %s" + filters + ' GROUP BY l.account_id')
            params = (tuple(accounts.ids),) + tuple(init_where_params)
            cr.execute(sql, params)
            for row in cr.dictfetchall():
                move_lines[row.pop('account_id')].append(row)


        # Prepare sql query base on selected parameters from wizard
        tables, where_clause, where_params = MoveLine._query_get()
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

        # Get move lines base on sql query and Calculate the total balance of move lines
        sql_sort = 'l.date'
        if sortby == 'sort_journal_partner':
            sql_sort = 'l.j_code, l.partner_name'
            
        sql = ('''SELECT 
                    l.lid as lid,
                    l.account_id AS account_id,
                    l.date AS ldate,
                    l.j_code AS lcode,
                    l.currency_id, 
                    l.amount_currency, 
                    l.currency_code,
                    l.line_ref AS lref, 
                    l.lname as lname,
                    l.memo AS memo,
                    COALESCE(l.debit,0) AS debit,
                    COALESCE(l.credit,0) AS credit, 
                    COALESCE(l.balance,0) AS balance, 
                    l.move_name AS move_name,
                    l.outlet_name AS outlet_name,
                    l.analytic_account_name AS analytic_account_name,
                    l.partner_name AS partner_name

                FROM {table_name} l 
                
                WHERE l.account_id IN %s ''' + filters + '''
                ''').format(table_name=self.table_id.name)
                #ORDER BY ''' + sql_sort)

#             sql_sort = 'l.date, l.move_id'
#             if sortby == 'sort_journal_partner':
#                 sql_sort = 'j.code, p.name, l.move_id'
#             sql = ('SELECT l.id AS lid, l.account_id AS account_id, l.date AS ldate, j.code AS lcode, l.currency_id, l.amount_currency, l.ref AS lref, l.name AS lname, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance,\
#                 m.name AS move_name, c.symbol AS currency_code, p.name AS partner_name\
#                 FROM account_move_line l\
#                 JOIN account_move m ON (l.move_id=m.id)\
#                 LEFT JOIN res_currency c ON (l.currency_id=c.id)\
#                 LEFT JOIN res_partner p ON (l.partner_id=p.id)\
#                 JOIN account_journal j ON (l.journal_id=j.id)\
#                 JOIN account_account acc ON (l.account_id = acc.id) \
#                 WHERE l.account_id IN %s ' + filters + ' GROUP BY l.id, l.account_id, l.date, j.code, l.currency_id, l.amount_currency, l.ref, l.name, m.name, c.symbol, p.name ORDER BY ' + sql_sort)
        
        params = (tuple(accounts.ids),) + tuple(where_params)
        
        
        cr.execute(sql, params)
        
        for row in cr.dictfetchall():
#             balance = 0
#             for line in move_lines.get(row['account_id']):
#                 balance += line['debit'] - line['credit']
#             row['balance'] += balance
            move_lines[row.pop('account_id')].append(row)

        # Calculate the debit, credit and balance for Accounts
        account_res = []
        for account in accounts:
            currency = account.currency_id and account.currency_id or account.company_id.currency_id
            res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance'])
            res['code'] = account.code
            res['name'] = account.name
            res['move_lines'] = move_lines[account.id]
#             res['currency'] = ''
#             if currency:
#                 res['currency'] = currency.symbol
#             for line in res.get('move_lines'):
#                 res['debit'] += line['debit']
#                 res['credit'] += line['credit']
#                 res['balance'] = line['balance']
#                 line['currency'] = ''
#                 if currency:
#                     line['currency'] = currency.symbol
            if display_account == 'all':
                account_res.append(res)
            if display_account == 'movement' and res.get('move_lines'):
                account_res.append(res)
            if display_account == 'not_zero' and not currency.is_zero(res['balance']):
                account_res.append(res)

        return account_res
    
    
    @api.multi
    def _print_general_ledger_excel_report(self,data):
        self.model = data.get('model')
        if data['form'].get('initial_balance') and not data['form'].get('date_from'):
            raise UserError(_("You must define a Start Date"))
        docs = self.env[self.model].browse(self.env.context.get('active_ids', []))
        display_account = data['form'].get('display_account')
        sortby = data['form'].get('sortby', 'sort_date')
        init_balance = data['form'].get('initial_balance', True)
        
        accounts = docs if self.model == 'account.account' else self.env['account.account'].search([])
        
        return self.with_context(data['form'].get('used_context',{}))._get_account_move_entry(accounts, init_balance, sortby, display_account)
    
    @api.multi
    def check_general_ledger_report_excel(self):
        self.ensure_one()
        context = self._context
        data = {}
        company_name = ''
        user = self.env['res.users'].browse(context.get('uid'))
        if user:
            company_name = user.company_id.name
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        # read fields which require for where clause
        data['form'] = self.read(['date_from', 'initial_balance', 'date_to','display_account','sortby'])[0]
        used_context = self._build_contexts(data)
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        
        codes = []
        if data['form'].get('journal_ids', False):
            codes = [journal.code for journal in self.env['account.journal'].search([('id', 'in', data['form']['journal_ids'])])]
        print_journal = ', '.join([ lt or '' for lt in codes ])
        
        account_res = self._print_general_ledger_excel_report(data)
        fl = StringIO()
        workbook = xlsxwriter.Workbook(fl, {'in_memory': True})
        worksheet = workbook.add_worksheet('General-ledger')
        style = workbook.add_format({'bold':  True, 'font_size': 10})
        
        label_style = workbook.add_format({'bold':  True, 'font_size': 10})
        
        style_right_align = workbook.add_format()
        style_right_align.set_align('right')
        
        style_bold_right_align = workbook.add_format({'bold':  True, 'font_size': 10})
        style_bold_right_align.set_align('right')
        
        has_currency_group = self.user_has_groups('base.group_multi_currency')
        
        worksheet.write(0,0, company_name + ' : ' + 'General ledger',style)
#         worksheet.write(10,1,'Journals :',label_style)
#         worksheet.merge_range('B11:K12',print_journal)
        
        
        
        worksheet.write(2,0,'Display Account:',label_style)
        worksheet.write(3,0,data['form']['display_account'])
        
        #for now all default as we consolidate all lines in table
        target_move_str = 'all'
#         if data['form']['target_move'] == 'all':
#             target_move_str = 'All Entries'
#         elif data['form']['target_move'] == 'posted':
#             target_move_str = 'All Posted Entries'
            
        worksheet.write(2,2,'Target Moves:',label_style)
        worksheet.write(3,2,target_move_str)
        
        sort_by_str = ''
        if data['form']['sortby'] == 'sort_date':
            sort_by_str = 'Date'
        elif data['form']['sortby'] == 'sort_journal_partner':
            sort_by_str = 'Journal and Partner'
            
        worksheet.write(2,4,'Sorted By:',label_style)
        worksheet.write(3,4,sort_by_str)
        
        if data['form']['date_from']:
            worksheet.write(2,6,'Date from :',label_style)
            worksheet.write(2,7,data['form']['date_from'])
        if data['form']['date_to']:
            worksheet.write(3,6,'Date to :',label_style)
            worksheet.write(3,7,data['form']['date_to'])
        
        def print_header(col,label_style):
            worksheet.write(col,0,'Date',label_style)
            worksheet.write(col,1,'Account',label_style)
            worksheet.write(col,2,'JRNL',label_style)
            worksheet.write(col,3,'Outlet Name',label_style)
            worksheet.write(col,4,'Analytic Account',label_style)
            worksheet.write(col,5,'Partner Name',label_style)
            worksheet.write(col,6,'Doc No',label_style)
            worksheet.write(col,7,'Journal No',label_style)
            worksheet.write(col,8,'Description',label_style)
            worksheet.write(col,9,'Memo',label_style)
            worksheet.write(col,10,'Debit',label_style)
            worksheet.write(col,11,'Credit',label_style)
            worksheet.write(col,12,'Balance',label_style)
            worksheet.write(col,13,'Currency',label_style)
        
        print_header(5,label_style)
        
        row = 0
        colum = 7
        sheet_count = 1
        max_limit = 1048576 - colum

        for res in account_res:
            
            # this code is to change the sheet when row limit over of xlswriter
            if colum > max_limit:
                max_limit += max_limit
                colum = 1
                worksheet = workbook.add_worksheet('General-ledger-'+str(sheet_count))
                sheet_count += 1
                print_header(0,label_style)
 
            worksheet.write(colum,row,res.get('code') + ' ' + res.get('name'),label_style)
            row += 9
            
            debit_index = [colum,row]
            worksheet.write(colum,row, "%.2f" % float(round(res.get('debit', 0),2)) ,label_style)
            row += 1
            
            credit_index = [colum,row]
            worksheet.write(colum,row, "%.2f" % float(round(res.get('credit', 0),2)) ,label_style)
            row += 1
                        
            balance_index = [colum,row]
            worksheet.write(colum,row, "%.2f" % float(round(res.get('balance', 0),2)) ,label_style)
            colum += 1
            row = 0
            
            account_line_debit_total = 0.00
            account_line_credit_total = 0.00
            account_line_balance_total = 0.00
            running_balance = 0
            for line in res['move_lines']:
                worksheet.write(colum,row,line.get('ldate'))
                row += 1
                worksheet.write(colum,row,res.get('code') + ' ' + res.get('name'))
                row += 1
                worksheet.write(colum,row,line.get('lcode'))
                row += 1
                worksheet.write(colum,row,line.get('outlet_name'))
                row += 1
                worksheet.write(colum,row,line.get('analytic_account_name'))
                row += 1
                worksheet.write(colum, row, line.get('partner_name') or '')
                row += 1
                worksheet.write(colum,row,line.get('lref') or '')
                row += 1
                worksheet.write(colum,row,line.get('move_name'))
                row += 1
                worksheet.write(colum,row,line.get('lname'))
                row += 1
                worksheet.write(colum,row,line.get('memo'))
                row += 1
                
                account_line_debit_total += float(round(line.get('debit', 0),2))
                worksheet.write(colum,row, "%.2f" % float(round(line.get('debit', 0),2)), style_right_align)
                row += 1
                
                account_line_credit_total += float(round(line.get('credit', 0),2))
                worksheet.write(colum,row, "%.2f" % float(round(line.get('credit', 0),2)), style_right_align)
                row += 1
                
                account_line_balance_total += float(round(line.get('balance', 0),2))
                
                balance = float(round(line.get('debit', 0),2)) - float(round(line.get('credit', 0),2))
                running_balance = running_balance + balance
                
                worksheet.write(colum,row, "%.2f" % float(running_balance), style_right_align)
                
                if has_currency_group:
                    row += 1
                    amount_currency_str = ''
                    if line.get('amount_currency') and line['amount_currency'] > 0.00:
                        amount_currency_str = str(line['amount_currency']) + line.get('currency_code','') or ''
                        worksheet.write(colum,row,amount_currency_str)
                colum += 1
                     
                row = 0
                
            # this is account vise main total
            worksheet.write(debit_index[0],debit_index[1],"%.2f" % account_line_debit_total,style_bold_right_align)
            worksheet.write(credit_index[0],credit_index[1],"%.2f" % account_line_credit_total,style_bold_right_align)
            worksheet.write(balance_index[0],balance_index[1],"%.2f" % account_line_balance_total,style_bold_right_align)
                
         
        workbook.close()
        fl.seek(0)
        buf = base64.encodestring(fl.read())
        filename = "General-ledger"
        self.write({'file': buf,'name': filename})
        return { 
            'type' : 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=account.report.general.ledger&field=file&id=%s&filename=%s.xls'%(self.id, filename),
            'target': 'self',
            }

class refresh_consolidation_wizard(models.TransientModel):
    _name = "refresh.consolidation.wizard"
    
    @api.multi
    def wizard_refresh_gl_consolidation_table(self):
        self.refresh_gl_consolidation_table()
    
    @api.model
    def refresh_gl_consolidation_table(self):
        query_start_time = datetime.now()
        gl_period = self.env['gl.period'].search([])[0]
        
        cr = self.env.cr
        # common method call to create table
        self.env['gl.archive.table'].create_sql_table(gl_period.table_id.name)
        
        # USE SUDO TO HAVE ALL ACCOUNT FROM BOTH COMPANY (CONSOLIDATION CONFIG IS COMPANY WISE)
        date_outlet_account_ids = []
        for date_outlet in self.env['gl.consolidation.config'].sudo().search([('consolidation_method','=','date_and_outlet')]):
            date_outlet_account_ids += [x.id for x in date_outlet.account_ids]
            
        date_analytic_account_ids = []
        for date_analytic in self.env['gl.consolidation.config'].sudo().search([('consolidation_method','=','date_and_analytic_account')]):
            date_analytic_account_ids += [x.id for x in date_analytic.account_ids]
            
        date_account_ids = []
        for date_account in self.env['gl.consolidation.config'].sudo().search([('consolidation_method','=','date')]):
            date_account_ids += [x.id for x in date_account.account_ids]
        
        remaining_accounts =  self.env['account.account'].sudo().search([('id','not in',list(set(date_outlet_account_ids))
                                                                   + list(set(date_analytic_account_ids))
                                                                   + list(set(date_account_ids))
                                                                   )])
        
        if not gl_period or not list(set(date_outlet_account_ids)) + list(set(date_analytic_account_ids)) + list(set(date_account_ids)):
            raise UserError('Consolidation configuration is missing !')
        
        remaining_account_ids = [x.id for x in remaining_accounts]
        
        gl_consolidation_query = """
            insert into {table_name} (
                                            lid,
                                            account_id,
                                            date,
                                            j_code,
                                            currency_id,
                                            amount_currency,
                                            currency_code,
                                            line_ref,
                                            lname,
                                            debit,
                                            credit,
                                            balance,
                                            move_name,
                                            memo,
                                            outlet_name,
                                            analytic_account_name,
                                            partner_name
                                            )

            select     
                    data.lid as lid,
                    data.account_id AS account_id,
                    data.ldate AS ldate,
                    data.lcode AS lcode,
                    data.currency_id, 
                    sum(COALESCE(data.amount_currency,0)) as amount_currency,
                    data.currency_code AS currency_code,
                    data.lref AS lref,  
                    data.lname AS lname,
                    sum(COALESCE(data.debit,0)) AS debit,
                    sum(COALESCE(data.credit,0)) AS credit, 
                    sum(COALESCE(data.balance,0)) AS balance,
                    data.move_name AS move_name,
                    data.memo AS memo,
                    data.outlet_name as outlet_name,
                    data.analytic_account_name as analytic_account_name,
                    data.partner_name as partner_name

            from (
                    -- THIS PART IS FOR DATE+OUTLET GROUPBY
                    SELECT 
                        0 AS lid,
                        l.account_id AS account_id,
                        l.date AS ldate,
                        j.code AS lcode,
                        l.currency_id, 
                        l.amount_currency,
                        c.symbol AS currency_code, 
                         '' AS lref,  
                        '' AS lname,
                        COALESCE(l.debit,0) AS debit,
                        COALESCE(l.credit,0) AS credit, 
                        COALESCE(l.debit,0) - COALESCE(l.credit, 0) AS balance, 
                        '' AS move_name,
                        '' AS memo,
                        outlet.name as outlet_name,
                        '' as analytic_account_name,
                        '' as partner_name

                    FROM account_move_line l            
                    JOIN account_move m ON (l.move_id=m.id)   
                    LEFT JOIN account_analytic_account ana on (l.analytic_account_id = ana.id)
                    LEFT JOIN br_multi_outlet_outlet outlet on (ana.id = outlet.analytic_account_id )
                    JOIN account_journal j ON (l.journal_id=j.id)            
                    JOIN account_account acc ON (l.account_id = acc.id)             
                    LEFT JOIN res_currency c ON (l.currency_id=c.id)
            
                    WHERE l.account_id IN %s
                    and l.date >= '{date_from}' and l.date <= '{date_to}'
                   
                    --GROUP BY l.account_id, j.code, l.currency_id, l.amount_currency, l.date, c.symbol, p.name ORDER BY l.date
                UNION ALL 
                    
                    -- THIS PART IS FOR DATE+ANALYTIC ACCOUTN GROUPBY
                    SELECT 
                        0 AS lid,
                        l.account_id AS account_id,
                        l.date AS ldate,
                        j.code AS lcode,
                        l.currency_id,
                        l.amount_currency,
                        c.symbol AS currency_code,
                        '' AS lref,  
                        '' AS lname,
                        COALESCE(l.debit,0) AS debit,
                        COALESCE(l.credit,0) AS credit, 
                        COALESCE(l.debit,0) - COALESCE(l.credit, 0) AS balance, 
                        '' AS move_name,
                        '' AS memo,
                        '' as outlet_name,
                        ana.name as analytic_account_name,
                        '' as partner_name

                    FROM account_move_line l            
                    JOIN account_move m ON (l.move_id=m.id)   
                    LEFT JOIN account_analytic_account ana on (l.analytic_account_id = ana.id)
                    JOIN account_journal j ON (l.journal_id=j.id)            
                    JOIN account_account acc ON (l.account_id = acc.id)
                    LEFT JOIN res_currency c ON (l.currency_id=c.id)             
                    
                    WHERE l.account_id IN %s
                    and l.date >= '{date_from}' and l.date <= '{date_to}'
                        
                    --GROUP BY l.account_id, j.code, l.currency_id, l.amount_currency, l.ref, l.date, c.symbol, p.name ORDER BY l.date
                UNION ALL
    
                    -- THIS PART IS FOR DATE GROUPBY
                    SELECT 
                        0 AS lid,
                        l.account_id AS account_id,
                        l.date AS ldate,
                        j.code AS lcode,
                        l.currency_id, 
                        l.amount_currency,
                        c.symbol AS currency_code,
                        '' AS lref,
                        '' AS lname,
                        COALESCE(l.debit,0) AS debit,
                        COALESCE(l.credit,0) AS credit, COALESCE(l.debit,0) - COALESCE(l.credit, 0) AS balance, 
                        '' AS move_name,
                        '' AS memo,
                        '' as outlet_name,
                        '' as analytic_account_name,
                        '' as partner_name
    
                    FROM account_move_line l            
                    JOIN account_move m ON (l.move_id=m.id)           
                    JOIN account_journal j ON (l.journal_id=j.id)            
                    JOIN account_account acc ON (l.account_id = acc.id)
                    LEFT JOIN res_currency c ON (l.currency_id=c.id)
                    
                    WHERE l.account_id IN %s
                    and l.date >= '{date_from}' and l.date <= '{date_to}'
           
                UNION ALL
                    
                    -- THIS PART IS FOR WITHOUT CONSOLIDATION
                    SELECT 
                        l.id AS lid,  
                        l.account_id AS account_id, 
                        l.date AS ldate,
                        j.code AS lcode, 
                        l.currency_id, 
                        l.amount_currency,
                        c.symbol AS currency_code,
                        l.ref AS lref, 
                        l.name AS lname, 
                        COALESCE(l.debit,0) AS debit, 
                        COALESCE(l.credit,0) AS credit, 
                        COALESCE(l.debit,0) - COALESCE(l.credit, 0) AS balance,
                        m.name AS move_name,
                        m.memo AS memo, 
                        '' as outlet_name,
                        ana.name as analytic_account_name,
                        rp.name as partner_name
                        
                     FROM account_move_line l
                     JOIN account_move m ON (l.move_id=m.id)
                     LEFT JOIN account_analytic_account ana on (l.analytic_account_id = ana.id)
                     LEFT JOIN res_partner rp ON (l.partner_id=rp.id)
                     JOIN account_journal j ON (l.journal_id=j.id)
                     JOIN account_account acc ON (l.account_id = acc.id)
                     LEFT JOIN res_currency c ON (l.currency_id=c.id)
                      
                     WHERE l.account_id IN %s
                     and l.date >= '{date_from}' and l.date <= '{date_to}'
                     
            ) as data
            GROUP BY data.lid, data.account_id, data.lcode, data.currency_id, data.ldate, data.lref, data.lname, data.move_name, data.memo, data.currency_code, data.analytic_account_name, data.outlet_name, data.partner_name
        
            ORDER BY  data.ldate

        """.format(date_from = gl_period.date_from,
                   date_to = gl_period.date_to,
                   table_name=gl_period.table_id.name)

        params = (tuple(date_outlet_account_ids or [0]),) +  \
                (tuple(date_analytic_account_ids or [0]),) + \
                (tuple(date_account_ids or [0]),) + \
                (tuple(remaining_account_ids or [0]),)
                
        cr.execute(gl_consolidation_query, params)
        
        cr.execute("select count(*) from %s "% gl_period.table_id.name)
        rows_affected = cr.fetchone()[0]
        
        query_end_time = datetime.now()
        self.env['gl.consolidation.log'].create({'date':datetime.now().date(),
                                                 'start_time': query_start_time,
                                                 'end_time':query_end_time,
                                                 'type': 'consolidation',
                                                 'rows_affected':rows_affected,
                                                 'table_id':gl_period.table_id.id,
                                                 'user_id': self.env.user.id})
        
        
