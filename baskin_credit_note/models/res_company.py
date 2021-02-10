from openerp import models, fields, api, _
from openerp.exceptions import Warning
from openerp import SUPERUSER_ID

class res_company(models.Model):
    _inherit = 'res.company'
    
    bulk_refund_product = fields.Many2one('product.product', string="Bulk Refund Product")