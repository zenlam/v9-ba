# -*- coding: utf-8 -*-
from openerp import models, fields, api


class Purchase_Requisition(models.Model):
    _inherit = "purchase.requisition"

    name_related = fields.Char(string="Call for Tenders Reference", related="name", readonly=1)