from openerp import api, models, fields, _


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_mng_approval = fields.Boolean(string=_("Require Manager Approval"), default=False)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.one
    def _get_allow_validate(self):
        group_stock_manager_id = self.env.ref('stock.group_stock_manager').id
        user_groups = self.env.user.groups_id
        for group in user_groups:
            if group.id == group_stock_manager_id:
                self.allow_validate = True
                return
        self.allow_validate = not (self.picking_type_id.is_mng_approval or self.location_id.usage == 'inventory' or self.location_dest_id.usage == 'inventory')

    allow_validate = fields.Boolean(compute='_get_allow_validate')
