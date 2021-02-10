from openerp import api, models, fields


def _get_quants(self):
    """Get available product lot in stock by location, product and vendor"""
    dom = [('reservation_id', '=', False)]
    location_id = self.env.context.get('location_id', False)
    location = self.env['stock.location'].browse(location_id)
    quants = self.env['stock.quant']
    if location.usage == 'internal':
        fields = ['location_id', 'product_id', 'vendor_id', 'lot_id']
        for f in fields:
            if self.env.context.get(f, False):
                dom.append((f, '=', self.env.context.get(f)))
        quants = self.env['stock.quant'].search(dom)
    return quants


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    # name = fields.Char('Expiry Date', required=True, help="Unique Expiry Date", oldname='name')
    removal_date = fields.Datetime('Expiry Date',help='This is the date on which the goods with this Serial Number should be removed from the stock.', oldname='removal_date')

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        self._set_domain(args)
        return super(StockProductionLot, self).search(args, offset=offset, limit=limit, order=order, count=count)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        self._set_domain(args)
        return super(StockProductionLot, self).name_search(name, args=args, operator=operator, limit=limit)

    def _set_domain(self, args):
        """Get available product lot in stock by location, product and vendor"""
        if self.env.context.get('filter_lot', False):
            dest_location = self.env['stock.location'].browse(self.env.context['dest_location_id'])
            if not dest_location.damage_location:
                quants = _get_quants(self)
                if quants:
                    lot_ids = [quant.lot_id.id for quant in quants if quant.lot_id]
                    for arg in args:
                        field = arg[0]
                        if field == 'id':
                            filter_ids = arg[2]
                            if isinstance(filter_ids, list):
                                filter_ids.extend(lot_ids)
                            break
                    else:
                        args.extend([(u'id', u'in', lot_ids)])


# TODO: move this elsewhere
class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _set_domain(self, args):
        """Get available product lot in stock by location, product and vendor"""
        super(ResPartner, self)._set_domain(args)
        if self.env.context.get('filter_partner', False):
            quants = _get_quants(self)
            if quants:
                args.extend([('id', 'in', [quant.vendor_id.id for quant in quants if quant.vendor_id])])
