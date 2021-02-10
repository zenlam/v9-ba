from openerp import models, api, fields


class StockInventoryAdjustmentReview(models.TransientModel):
    _name = 'stock.inventory.adjustment.review'

    inventory_case = fields.Selection(selection=[
        ('1st_degree', '1st Degree'),
        ('2nd_degree', '2nd Degree'),
        ('no_case', 'No Case')
    ])

    @api.multi
    def set_case(self):
        inventory_ids = self.env.context.get('active_ids', False)
        if inventory_ids:
            inventories = self.env['stock.inventory'].browse(inventory_ids)
            todo = self.env['stock.inventory']
            for inv in inventories:
                if inv.state == 'done':
                    todo |= inv
        ir_model_data = self.env['ir.model.data']
        view_id = ir_model_data.get_object_reference('br_inventory_adjustment', 'inventory_set_action_form')[1]
        ctx = self.env.context.copy()
        ctx['inventory_ids'] = todo.ids
        ctx['inventory_case'] = self.inventory_case

        return {
            'name': 'Set Inventory Action',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.inventory.set.action',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'target': 'new',
            'context': ctx,
        }
