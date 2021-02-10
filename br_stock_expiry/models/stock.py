from openerp import models, api, _


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _check_to_pack(self, ops):
        if ops.location_id.manage_expirydate:
            return super(StockMove, self)._check_to_pack(ops)
        else:
            return ops.pack_lot_ids and ops.location_id.usage == 'supplier'


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    def _set_domain(self, args):
        """Get available product lot in stock by location, product and vendor"""
        location_id = self.env.context.get('location_id', False)
        location = self.env['stock.location'].browse(location_id)
        if location and not location.manage_expirydate:
            return args
        return super(StockProductionLot, self)._set_domain(args)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _check_group_by_vendor(self, picking):
        if not picking.location_id.manage_expirydate:
            return False
        return True