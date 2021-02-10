# -*- coding: utf-8 -*-
from openerp import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class ReverseTransferReasonCategory(models.Model):
    _name = "reverse.transfer.reason.category"
    
    name = fields.Char('Reason Category', required=True)
    type_code = fields.Selection([('incoming', 'Suppliers'), ('outgoing', 'Customers'), ('internal', 'Internal')], 'type', required=True)
    need_remarks = fields.Boolean('Need Remarks')
    active = fields.Boolean('Active', default=True)
    