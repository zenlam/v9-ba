# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError

class gl_consolidation_log(models.Model):
    _name = 'gl.consolidation.log'
    _order = 'date desc'
    
    type = fields.Selection([('consolidation','Consolidation'),('clone','Clone')], string="Type")
    date = fields.Date("Date")
    start_time = fields.Datetime("Start Time")
    end_time = fields.Datetime("End Time")
    table_id = fields.Many2one('gl.archive.table', string="Table")
    rows_affected = fields.Integer('Rows Affected')
    user_id = fields.Many2one('res.users',string='User')
