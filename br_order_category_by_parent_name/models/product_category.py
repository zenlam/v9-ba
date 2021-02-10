from openerp.osv import osv, fields
from openerp import api
from openerp.addons.product.product import product_category

class br_product_category(osv.osv):
    _inherit = 'product.category'

    _columns = {
        'complete_name': fields.function(product_category._name_get_fnc, type="char", string='Name', store=True),
    }

    _order = 'complete_name'
