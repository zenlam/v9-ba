# -*- coding: utf-8 -*-

from openerp import models, fields, api

class pos_config(models.Model):
    _inherit = 'pos.config'

    discount_promotion_bundle_id = fields.Many2one('product.product', 'Bundle Discount',
                                                    domain="[('available_in_pos', '=', True)]",
                                                    help='The product used to model the discount')
    discount_promotion_product_id = fields.Many2one('product.product', 'Product Discount',
                                                    domain="[('available_in_pos', '=', True)]",
                                                    help='The product used to model the discount')