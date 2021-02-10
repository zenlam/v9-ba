from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError

class res_currency_rate(models.Model):
    _inherit = 'res.currency.rate'
    
    @api.one
    @api.constrains('name','currency_id','company_id')
    def _check_rate_date(self):
        if self.name and self.currency_id:
            date = self.name.split(' ')[0]
            start_datetime = date + ' 00:00:00'
            end_datetime = date + ' 23:59:59'
            other_rate = self.search([('id','!=',self.id),
                         ('currency_id','=',self.currency_id.id),
                         ('name','>=',start_datetime),
                         ('name','<=',end_datetime)]) 
            if other_rate:
                raise ValidationError(_('Rate is already exist for this date !'))