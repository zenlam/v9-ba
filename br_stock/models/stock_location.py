from openerp import fields, models, api, _


class stock_location(models.Model):

    _inherit = 'stock.location'

    br_address = fields.Text(_("Address"))
    br_analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                             track_visibility='always')
    damage_location = fields.Boolean(compute='_check_damage_location', string="Is Damage Location", store=True)

    pos_config_ids = fields.One2many(comodel_name='pos.config', inverse_name='stock_location_id', string="Point Of Sales")
    warehouse_id = fields.Many2one(comodel_name='stock.warehouse', string="Warehouse", compute='_get_warehouse_id', store=True)

    @api.depends('parent_left','parent_right')
    @api.multi
    def _get_warehouse_id(self):
        for l in self:
            l.warehouse_id = l.get_warehouse(l)

    @api.depends('usage', 'scrap_location')
    @api.multi
    def _check_damage_location(self):
        for l in self:
            l.damage_location = l.usage == 'inventory' and l.scrap_location

    def get_loss_location(self):
        # This function should belong to stock.warehouse
        warehouse_id = self.get_warehouse(self)
        if warehouse_id:
            warehouse = self.env['stock.warehouse'].browse(warehouse_id)
            if warehouse.loss_dest_location_id:
                return warehouse.loss_dest_location_id
            # loss_location = self.env['stock.location'].search([
            #     ('location_id', 'child_of', warehouse.view_location_id.id),
            #     ('usage', '=', 'inventory'),
            #     ('scrap_location', '=', False),
            # ], limit=1)
            # if loss_location:
            #     return loss_location
        return False

    def get_outlet(self):
        warehouse_id = self.get_warehouse(self)
        if warehouse_id:
            outlet = self.env['br_multi_outlet.outlet'].search([('warehouse_id', '=', warehouse_id)])
            if outlet:
                return outlet
        return False

    def get_analytic_account(self):
        """
        # By default get analytic account from destination location,
        # when there is no analytic account is configured on location then get it from outlet
        @param dest_location: object (stock.location)
        @return: object (account.analytic.account)
        """
        analytic_account_id = False
        if self.br_analytic_account_id:
            analytic_account_id = self.br_analytic_account_id.id
        else:
            warehouse = self.env['stock.location'].get_warehouse(self)
            if warehouse:
                outlet = self.env['br_multi_outlet.outlet'].search(([('warehouse_id', '=', warehouse)]))
                if outlet:
                    analytic_account_id = outlet[0].analytic_account_id.id
        return analytic_account_id

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    is_main_warehouse = fields.Boolean('Is Main Warehouse', help="Need to check this when warehouse is Main Warehouse "
                                                                 "like Iglo, Batu Caves..")

    @api.multi
    def get_outlet(self):
        self.ensure_one()
        outlet = self.env['br_multi_outlet.outlet'].search([('warehouse_id', '=', self.id)])
        return outlet