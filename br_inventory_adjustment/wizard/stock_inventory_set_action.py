from openerp import models, api, fields


class StockInventoryAction(models.TransientModel):
    _name = 'stock.inventory.set.action'

    action_id = fields.Many2one(comodel_name='stock.inventory.action')

    @api.multi
    def set_action(self):
        inventory_ids = self.env.context['inventory_ids']
        state = self.env.context['inventory_case']
        inventory = self.env['stock.inventory'].browse(inventory_ids)
        inventory.write({'state': state, 'inventory_action_id': self.action_id.id, 'reviewer_id': self.env.user.id})
