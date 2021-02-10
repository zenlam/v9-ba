from openerp import fields, models, api, _
from openerp.exceptions import ValidationError


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    is_default = fields.Boolean(string=_("Default Supplier"), default=False)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        self._set_domain(args)
        return super(ProductSupplierinfo, self).name_search(name, args=args, operator=operator, limit=limit)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        self._set_domain(args)
        return super(ProductSupplierinfo, self).search(args, offset=offset, limit=limit, order=order, count=count)

    def _set_domain(self, args):
        """Filter vendor by product"""
        product_id = self.env.context.get('product_vendor_id', None)
        if product_id:
            product = self.env['product.product'].browse(product_id)
            args.extend([('product_tmpl_id', '=', product.product_tmpl_id.id)])