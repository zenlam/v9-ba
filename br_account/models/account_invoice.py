from openerp import models, api, fields, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError


class BRAccountAssetCategory(models.Model):
    _inherit = 'account.asset.category'

    br_asset_account = fields.Many2one('account.account', string="Asset Account")

BRAccountAssetCategory()


class BRAccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_move_create(self):
        for inv in self:
            if inv.move_id:
                continue
            if not inv.date_invoice:
                company_currency = inv.company_id.currency_id
                if inv.currency_id != company_currency and inv.tax_line:
                    raise UserError(_('No invoice date!'
                                      '\nThe invoice currency is not the same than the company currency.'
                                      ' An invoice date is required to determine the exchange rate to apply. '
                                      'Do not forget to update the taxes!'))
        res = super(BRAccountInvoice, self).action_move_create()
        return res

    def _get_invoice_name(self):
        journal = self.journal_id
        sequence = journal.sequence_id
        if self.type in ['out_refund', 'in_refund'] and journal.refund_sequence:
            sequence = journal.refund_sequence_id
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.model
    def create(self, vals):
        res = super(BRAccountInvoice, self).create(vals)
        if 'move_name' not in vals:
            res.write({'move_name': res._get_invoice_name()})
        return res


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.model
    def default_get(self, fields):
        res = super(AccountInvoiceLine, self).default_get(fields)
        partner_id = self.env.context.get('partner_id', False)
        if partner_id:
            res['account_analytic_id'] = self._get_analytic_account_by_partner(partner_id)
        return res

    def _get_analytic_account_by_partner(self, partner_id):
        analytic_account = self.env['account.analytic.account'].search([('partner_id', '=', partner_id)],
                                                                       limit=1)
        return analytic_account.id

    @api.multi
    def set_account_for_line(self):
        for line in self:
            type = line.invoice_id.type
            if type not in ('out_invoice', 'out_refund'):
                line.account_id = line.asset_category_id.br_asset_account or \
                                  line.product_id.categ_id.property_account_expense_categ_id
            else:
                fpos = line.invoice_id.fiscal_position_id
                company = line.invoice_id.company_id
                account = line.get_invoice_line_account(type, line.product_id, fpos, company)
                line.account_id = account

    @api.onchange('asset_category_id')
    def onchange_asset_category_id(self):
        super(AccountInvoiceLine, self).onchange_asset_category_id()
        if self.product_id:
            self.set_account_for_line()

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        result = super(AccountInvoiceLine, self)._onchange_uom_id()
        if self.product_id:
            self.set_account_for_line()
        return result

AccountInvoiceLine()
