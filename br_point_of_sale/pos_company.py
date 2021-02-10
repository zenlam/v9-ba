from openerp import fields, models


class br_res_company(models.Model):
    _inherit = 'res.company'

    rounding_product_id = fields.Many2one('product.product', string='Rounding Product')
