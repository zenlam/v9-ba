from openerp import models, fields, api, _


class br_res_users(models.Model):
    _inherit = 'res.users'

    outlet_ids = fields.Many2many(comodel_name='br_multi_outlet.outlet', string=_("Outlets"))
    warehouse_ids = fields.Many2many(comodel_name='stock.warehouse', string=_("Warehouses"))
    location_ids = fields.One2many(comodel_name='stock.location', string=_("Locations"), compute='_get_location_ids')
    picking_type_ids = fields.One2many(comodel_name='stock.picking.type', compute='_get_picking_type_ids')

    @api.multi
    def _get_location_ids(self):
        # User's locations are either children of configured warehouses or locations that not under any warehouses
        for u in self:
            domain = [
                '|',
                ('location_id', 'child_of', [x.view_location_id.id for x in u.warehouse_ids]),
                '!',
                ('location_id', 'child_of', [x.view_location_id.id for x in u.sudo().env['stock.warehouse'].search([('company_id', '=', u.company_id.id)])]),
            ]
            _context = self.env.context.copy()
            _context.update(user_filter=True)
            u.update({'location_ids': u.env['stock.location'].with_context(_context).search(domain).ids})

    @api.one
    def _get_picking_type_ids(self):
        domain = [
            ('warehouse_id', 'in', self.warehouse_ids.ids),
        ]
        self.picking_type_ids = self.env['stock.picking.type'].search(domain)