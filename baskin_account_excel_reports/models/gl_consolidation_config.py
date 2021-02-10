# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError
from datetime import datetime

CONSOLIDATION_METHODS = [('date_and_outlet','Consolidate into per outlet per day (one entry)'),
                         ('date_and_analytic_account','Consolidate into per analytic account per day (one entry)'),
                         ('date','Consolidate into per day (one entry)')
                         ]

class gl_consolidation_config(models.Model):
    _name = 'gl.consolidation.config'

    consolidation_method = fields.Selection(CONSOLIDATION_METHODS, string="Consolidation Method", required=True)
    account_ids = fields.Many2many('account.account', 'account_consolidation_rel', 'consolidation_id', 'account_id', string="Accounts", required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get('gl.consolidation.config'))
    
    @api.one
    @api.constrains('account_ids','consolidation_method')
    def _check_account_method_unique(self):
        # Constraint should be one account can not be associate with two methods
        if self.consolidation_method and  self.account_ids:
            other_config = self.search([('id','!=',self.id),
                                        ('consolidation_method','!=',self.consolidation_method)])
            account_names = []
            for config in other_config:
                for account in self.account_ids:
                    if account.id in [x.id for x in config.account_ids]:
                        account_names.append(account.name)
            if account_names:
                raise UserError(_('You can not configure "%s" for two different consolidation method !'% ', '.join(account_names)))

class gl_archive_table(models.Model):
    _name = 'gl.archive.table'
    
    name = fields.Char("New Table Name", required=True)
    
    @api.one
    @api.constrains('name')
    def _check_name_unique(self):
        if self.name:
            other_table = self.search([('id','!=',self.id),
                                        ('name','=',self.name)])
            if other_table:
                raise UserError(_('Table name should be unique !'))
            
    def create_sql_table(self,table_name):
        cr = self.env.cr
        cr.execute("DROP TABLE IF EXISTS %s"%table_name)
        cr.execute(""" 
                    CREATE TABLE %s (
                        
                        lid integer,
                        account_id integer,
                        date date,
                        j_code char(120),
                        currency_id integer,
                        amount_currency float,
                        currency_code text,
                        line_ref text,
                        lname text,
                        debit float,
                        credit float,
                        balance float,
                        move_name text,
                        memo text,
                        outlet_name text,
                        analytic_account_name text,
                        partner_name text
                    )"""%table_name)
        return True
        
            
    @api.model
    def create(self, vals):
        self.create_sql_table(vals.get('name'))
        return super(gl_archive_table, self).create(vals)

    @api.multi
    def write(self, vals):
        cr = self.env.cr
        for record in self:
            cr.execute("DROP TABLE IF EXISTS %s"%record.name)
            self.create_sql_table(vals.get('name'))
        return super(gl_archive_table, self).write(vals)
    
    @api.multi
    def unlink(self):
        cr = self.env.cr
        for record in self:
            cr.execute("DROP TABLE IF EXISTS %s"%record.name)
        return super(gl_archive_table, self).unlink()
    
    @api.multi
    def clone_data_between_tables(self):
        query_start_time = datetime.now()
        cr = self.env.cr
        cr.execute("delete from %s "%(self.name))
        cr.execute("INSERT INTO %s SELECT * FROM %s"%(self.name, 'gl_consolidated_data'))
        
        cr.execute("select count(*) from %s "% self.name)
        rows_affected = cr.fetchone()[0]
        
        query_end_time = datetime.now()
        self.env['gl.consolidation.log'].create({'date':datetime.now().date(),
                                                 'start_time': query_start_time,
                                                 'end_time':query_end_time,
                                                 'type': 'clone',
                                                 'rows_affected':rows_affected,
                                                 'table_id':self.id,
                                                 'user_id': self.env.user.id})
        return True

    
class gl_period(models.Model):
    _name = 'gl.period'
    
    date_from = fields.Date("Date From")
    date_to = fields.Date("Date To")
    table_id = fields.Many2one('gl.archive.table', string="Table Name", required=True) 
    
class gl_period_config(models.TransientModel):
    _inherit = 'res.config.settings'
    _name = 'gl.period.config'

    date_from = fields.Date("Date From")
    date_to = fields.Date("Date To")
    table_id = fields.Many2one('gl.archive.table', string="Table Name", required=True)

    @api.model
    def get_default_date_values(self, fields):
        gl_period = self.env['gl.period'].search([])[0]
        return {
            'date_from': gl_period.date_from,
            'date_to': gl_period.date_to,
            'table_id': gl_period.table_id.id,
        }

    @api.one
    def set_date_values(self):
        gl_period = self.env['gl.period'].search([])[0]
        gl_period.date_from = self.date_from
        gl_period.date_to = self.date_to
        gl_period.table_id = self.table_id.id

    
    