from openerp import fields, models, api, _
import pytz
from datetime import datetime, timedelta
import base64

class gto_log(models.Model):
    _name = "log.gto.report"
    _order = 'id desc'
    file_name = fields.Char('File Name')
    date_transfer = fields.Datetime('Date Transfer')
    state = fields.Selection([('done', 'Done'), ('except', 'Except')], 'State')
    info = fields.Text('Note')
    company_id = fields.Many2one('res.company', 'Company')
    outlet_ids = fields.Many2one(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')
    file = fields.Binary('File to Download', readonly=True)
    result = fields.Char(compute='get_result')

    @api.multi
    def get_result(self):
        for log in self:
            if log.file:
                log.result = base64.decodestring(log.file)

    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid,
                                                                                         'pos.session',
                                                                                         context=c),
    }