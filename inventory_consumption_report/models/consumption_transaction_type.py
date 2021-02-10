import time
from datetime import datetime, date, timedelta
from openerp import api, fields, models, exceptions, _

import logging
_logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

class consumption_transaction_type(models.Model):
    _name = 'consumption.transaction.type'
    
    name = fields.Selection([('retail_sales','Retail Sales'),
                             ('trade_sales','Trade Sales'),
                             ('intercompany_sales','Intercompany Sales'),
                             ('consumable_to_loss','Consumable to LOSS')], required=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, 
                                 default=lambda self: self.env['res.company']._company_default_get('consumption.transaction.type'))
    
    @api.multi
    def name_get(self):
        company_gssb = {
            'retail_sales': _('Retail Sales'),
            'trade_sales': _('Trade Sales (except MSPL)'),
            'intercompany_sales': _('Intercompany Sales to MSPL'),
            'consumable_to_loss': _('Consumable to LOSS'),
        }
        company_mspl = {
            'retail_sales': _('Retail Sales'),
            'trade_sales': _('Trade Sales (except GSSB)'),
            'intercompany_sales': _('Intercompany Sales to GSSB'),
            'consumable_to_loss': _('Consumable to LOSS'),
        }
        result = []
        for rec in self:
            if rec.company_id and rec.company_id.name.startswith('Golden'):
                result.append((rec.id, "%s" % (company_gssb[rec.name])))
            elif rec.company_id and rec.company_id.name.startswith('Mega'):
                result.append((rec.id, "%s" % (company_mspl[rec.name])))
            else:
                result.append((rec.id, "%s" % (rec.name)))
        return result