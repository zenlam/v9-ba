import time
from datetime import datetime, date, timedelta
from openerp import api, fields, models, exceptions, _

import logging
_logger = logging.getLogger(__name__)

class product_category(models.Model):
    _inherit = 'product.category'

    is_stockable_consumable = fields.Boolean('Expense Through Stock Count')

    @api.onchange('is_stockable_consumable')
    def onchange_is_stockable_consumable(self):
        if self.is_stockable_consumable is False:
            self.property_stock_account_loss_categ_id = False
            self.property_stock_account_excess_categ_id = False
