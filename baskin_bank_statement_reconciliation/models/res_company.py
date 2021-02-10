from openerp import models, fields, api, _
from openerp.exceptions import Warning
from openerp import SUPERUSER_ID

class res_company(models.Model):
    _inherit = 'res.company'
    
    bank_recon_sequence_id = fields.Many2one('ir.sequence', string="Bank Reconcile")