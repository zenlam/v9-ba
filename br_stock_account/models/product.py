# -*- coding: utf-8 -*-
from openerp import models, fields, api


class BRProductCategory(models.Model):
    _inherit = 'product.category'

    property_stock_account_loss_categ_id = fields.Many2one(comodel_name='account.account',  company_dependent=True,
                                                           string="Stock Adjustment - Loss")
    property_stock_account_excess_categ_id = fields.Many2one(comodel_name='account.account',  company_dependent=True,
                                                             string="Stock Adjustment - Excess")


BRProductCategory()
