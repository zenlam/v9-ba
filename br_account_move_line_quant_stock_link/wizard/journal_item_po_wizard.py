from openerp import models, fields, api, _
from openerp.exceptions import UserError


class journal_item_po_wizard(models.TransientModel):
    _name = 'journal.item.po.wizard'

    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)

    @api.multi
    def get_items(self):
        domain = [('date', '>=', self.from_date),
                  ('date', '<=', self.to_date),
                  ('account_id', '=', self.env.context.get('active_id'))
                  ]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Items',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'context' : {'search_default_group_purchase': 1},
            'domain': domain
        }
