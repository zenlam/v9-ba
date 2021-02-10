from openerp import api, fields, models, exceptions, _
import logging
_logger = logging.getLogger(__name__)

class stock_location(models.Model):
    _inherit = 'stock.location'
    
    is_loss_location = fields.Boolean('Is Loss Location')