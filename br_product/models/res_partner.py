from openerp import fields, models, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        self._set_domain(args)
        return super(ResPartner, self).name_search(name, args=args, operator=operator, limit=limit)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        self._set_domain(args)
        return super(ResPartner, self).search(args, offset=offset, limit=limit, order=order, count=count)

    def _set_domain(self, args):
        """Filter vendor by product"""
        if self.env.context.get('filter_on_inventory', False):
            if self.env.context.get('prod_lot_id', False):
                lot = self.env['stock.production.lot'].browse(self.env.context.get('prod_lot_id'))
                args.extend([('id', '=', lot.br_supplier_id.id)])
            elif self.env.context.get('product_vendor_id', False):
                product = self.env['product.product'].browse(self.env.context.get('product_vendor_id'))
                args.extend([('id', 'in', product.partner_ids.ids)])