# -*- coding: utf-8 -*-


from openerp import api, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.multi
    def action_view_invoice(self):
        result = super(PurchaseOrder, self).action_view_invoice()
        result['context'].update({'readonly_by_pass': ['account_analytic_id', 'date_due','asset_category_id']})
        return result
