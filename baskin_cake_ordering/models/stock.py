# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StockLocation(models.Model):
    _inherit = "stock.location"
    
    is_cake_location = fields.Boolean('Is Cake Location')
    
class StockMove(models.Model):
    _inherit = "stock.move"
    
    from_cake_location = fields.Boolean(related='location_id.is_cake_location', string='From Cake Location', store=True)