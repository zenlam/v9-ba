# -*- coding: utf-8 -*-

from openerp import models, fields, api

class pos_category(models.Model):
    _inherit = "pos.category"

    x_color = fields.Char('Color')
    x_background = fields.Char('Background')
