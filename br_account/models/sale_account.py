from openerp import fields, api, models, _

class sale_account(models.Model):
    _inherit = 'sale.order'

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        super(sale_account, self).onchange_partner_id()
        if self.partner_id:
            analytic_account = self.env['account.analytic.account'].search([('partner_id', '=', self.partner_id.id)], limit=1)
            if analytic_account:
                self.update({
                    'project_id': analytic_account.id
                })