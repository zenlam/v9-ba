from openerp import fields, api, models, _
from openerp.exceptions import ValidationError


class product_product(models.Model):
    _inherit = 'product.product'

    pricelist_item_ids = fields.One2many('product.pricelist.item', 'menu_id')


