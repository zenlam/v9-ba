from openerp import models, api, fields

TRANSFER_DIRECTION = [
    ('outlet_outlet', 'Outlet To Outlet'),
    ('warehouse_outlet', 'Warehouse To Outlet'),
    ('outlet_warehouse', 'Outlet To Warehouse'),
    ('warehouse_warehouse', 'Warehouse To Warehouse'),
    ('outlet_customer', 'Outlet To Customer'),
    ('warehouse_customer', 'Warehouse To Customer'),
    # update more states ?
    ('unknown', 'Unknown')
]


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    outlet_ids = fields.One2many(comodel_name='br_multi_outlet.outlet', inverse_name='warehouse_id', string="Outlets")


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    transfer_direction = fields.Selection(selection=TRANSFER_DIRECTION, string='Transfer Direction', compute='_get_transfer_direction', store=True)

    @api.depends('location_id', 'location_dest_id')
    @api.multi
    def _get_transfer_direction(self):
        types = {
            # format: (source location's type, destination location's type, source location is outlet location, destination location is outlet location)
            ('internal', 'internal', True, True): 'outlet_outlet',
            ('internal', 'internal', False, True): 'warehouse_outlet',
            ('internal', 'internal', True, False): 'outlet_warehouse',
            ('internal', 'internal', False, False): 'warehouse_warehouse',
            ('internal', 'customer', True, False): 'outlet_customer',
            ('internal', 'customer', False, False): 'warehouse_customer',
        }
        for sp in self:
            location = sp.location_id
            dest_location = sp.location_dest_id
            location_has_outlet = len(location.warehouse_id.outlet_ids) > 0
            dest_location_has_outlet = len(dest_location.warehouse_id.outlet_ids) > 0
            key = (location.usage, dest_location.usage, location_has_outlet, dest_location_has_outlet)
            if key in types:
                sp.transfer_direction = types[key]
            else:
                sp.transfer_direction = 'unknown'
