from openerp import models, fields, api, _


class ProductUom(models.Model):
    _inherit = 'product.uom'

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        uom_type = self.env.context.get('uom_type', False)
        if uom_type:
            product_id = self.env.context.get('product_id', False)
            if product_id:
                product = self.env['product.product'].browse(product_id)
                if uom_type == 'standard':
                    args.append(('id', '=', product.uom_id.id))
                if uom_type == 'purchase':
                    args.append(('is_po_default', '=', True))
                if uom_type == 'storage':
                    args.append(('is_storage', '=', True))
                if uom_type == 'distribution':
                    args.append(('is_distribution', '=', True))
        return super(ProductUom, self)._search(args, offset=offset, limit=limit, order=order, count=count,
                                               access_rights_uid=access_rights_uid)
