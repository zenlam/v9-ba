# -*- coding: utf-8 -*-

import time

from openerp import api, fields, models, _
from openerp.exceptions import ValidationError, RedirectWarning, UserError
from openerp.tools.float_utils import float_compare


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    actual_invoice_date = fields.Date(
                                'Actual Invoice Date',
                                readonly=True,
                                states={'draft': [('readonly', False)]},
                                index=True)
    date_invoice = fields.Date(default=fields.Date.context_today)
    need_gl_reclass = fields.Boolean('Need GL Reclass')
    gl_reclass_done = fields.Boolean('GL Reclass Done')
    account_analytic_id = fields.Many2one(
                            'account.analytic.account',
                            string='Analytic Account',
                            readonly=True,
                            states={'draft': [('readonly', False)]})

    # _sql_constraints = [
    #     ('number_uniq', 'unique(name, company_id)', 'Reference/Description must be unique per Company!'),
    # ]

    # @api.onchange('date_invoice')
    # def _onchange_date_invoice(self):
    #     self.actual_invoice_date = self.date_invoice

    @api.one
    def copy(self, default=None):
        default = dict(default or {})
        default['reference'] = False
        return super(AccountInvoice, self).copy(default)

    @api.constrains('date_invoice', 'actual_invoice_date')
    def _check_posting_date(self):
        for rec in self:
            if (self.date_invoice and self.actual_invoice_date) and (self.date_invoice < self.actual_invoice_date):
                raise ValidationError(_('Posting Date must be later or same as "Actual Bill Date". '))

    @api.onchange('need_gl_reclass')
    def _onchange_need_gl_reclass(self):
        if not self.need_gl_reclass:
            self.gl_reclass_done = False

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        account_analytic_id = False
        account_id = False
        payment_term_id = False
        fiscal_position = False
        bank_id = False
        p = self.partner_id
        company_id = self.company_id.id
        type = self.type
        if p:
            partner_id = p.id
            rec_account = p.property_account_receivable_id
            pay_account = p.property_account_payable_id
            if company_id:
                if p.property_account_receivable_id.company_id and \
                        p.property_account_receivable_id.company_id.id != company_id and \
                        p.property_account_payable_id.company_id and \
                        p.property_account_payable_id.company_id.id != company_id:
                    prop = self.env['ir.property']
                    rec_dom = [('name', '=', 'property_account_receivable_id'), ('company_id', '=', company_id)]
                    pay_dom = [('name', '=', 'property_account_payable_id'), ('company_id', '=', company_id)]
                    res_dom = [('res_id', '=', 'res.partner,%s' % partner_id)]
                    rec_prop = prop.search(rec_dom + res_dom) or prop.search(rec_dom)
                    pay_prop = prop.search(pay_dom + res_dom) or prop.search(pay_dom)
                    rec_account = rec_prop.get_by_record(rec_prop)
                    pay_account = pay_prop.get_by_record(pay_prop)
                    if not rec_account and not pay_account:
                        action = self.env.ref('account.action_account_config')
                        msg = _('Cannot find a chart of accounts for this company, You should configure it. \nPlease go to Account Configuration.')
                        raise RedirectWarning(msg, action.id, _('Go to the configuration panel'))

            if type in ('out_invoice', 'out_refund'):
                account_id = rec_account.id
                payment_term_id = p.property_payment_term_id.id

                analytic_default = self.env['account.analytic.default'].account_get(
                                                False,
                                                self.partner_id.id,
                                                self._uid, time.strftime('%Y-%m-%d'),
                                                company_id=self.env.user.company_id.id,
                                                context=self._context)
                if analytic_default:
                    account_analytic_id = analytic_default.analytic_id.id
                else:
                    analytic_account = self.env['account.analytic.account'].search([('partner_id', '=', self.partner_id.id)], limit=1)
                    if analytic_account:
                        account_analytic_id = analytic_account.id
                # account_analytic_id = rec_account.account_analytic_id.id
            else:
                account_id = pay_account.id
                payment_term_id = p.property_supplier_payment_term_id.id
                account_analytic_id = pay_account.account_analytic_id.id
            fiscal_position = p.property_account_position_id.id
            bank_id = p.bank_ids and p.bank_ids.ids[0] or False

        self.account_id = account_id
        self.payment_term_id = payment_term_id
        self.fiscal_position_id = fiscal_position
        self.account_analytic_id = account_analytic_id

        if type in ('in_invoice', 'in_refund'):
            self.partner_bank_id = bank_id

    # Load all unsold PO lines
    @api.onchange('purchase_id')
    def purchase_order_change(self):
        if not self.purchase_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.purchase_id.partner_id.id

        new_lines = self.env['account.invoice.line']
        for line in self.purchase_id.order_line:
            # Load a PO line only once
            if line in self.invoice_line_ids.mapped('purchase_line_id'):
                continue
            if line.product_id.purchase_method == 'purchase':
                qty = line.product_qty - line.qty_invoiced
                if qty == 0.0 and line.qty_received != 0.0 and line.qty_invoiced != 0.0:
                    continue
            else:
                qty = line.qty_received - line.qty_invoiced
                if qty == 0.0 and line.qty_received != 0.0 and line.qty_invoiced != 0.0:
                    continue
            if float_compare(qty, 0.0, precision_rounding=line.product_uom.rounding) <= 0:
                qty = 0.0

            taxes = line.taxes_id
            invoice_line_tax_ids = self.purchase_id.fiscal_position_id.map_tax(taxes)
            data = {
                'purchase_line_id': line.id,
                'name': line.name,
                'origin': self.purchase_id.origin,
                'uom_id': line.product_uom.id,
                'product_id': line.product_id.id,
                'account_id': self.env['account.invoice.line'].with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
                'price_unit': line.order_id.currency_id.compute(line.price_unit, self.currency_id, round=False),
                'quantity': qty,
                'discount': 0.0,
                'account_analytic_id': line.account_analytic_id.id,
                'invoice_line_tax_ids': invoice_line_tax_ids.ids
            }
            account = new_lines.get_invoice_line_account('in_invoice', line.product_id, self.purchase_id.fiscal_position_id, self.env.user.company_id)
            if account:
                data['account_id'] = account.id
            new_line = new_lines.new(data)
            new_line._set_additional_fields(self)
            new_lines += new_line

        self.invoice_line_ids += new_lines
        self.purchase_id = False
        return {}

    @api.multi
    def invoice_validate(self):
        res = super(AccountInvoice, self).invoice_validate()
        for invoice in self:
            if invoice.type == 'in_invoice' and not invoice.name:
                raise ValidationError(_('Memo field can not be empty!'))

            if invoice.type in ('in_invoice', 'in_refund') and not invoice.account_analytic_id:
                raise ValidationError(_('Please configure analytic account in Payable Account and re-select partner in this vendor bill!'))
            if invoice.type in ('out_invoice', 'out_refund') and  \
                    not invoice.account_analytic_id or any(not line.account_analytic_id for line in invoice.invoice_line_ids):
                raise ValidationError(_('Analytic Account not set for this partner!. \
                        \nPlease configure Analytic Default for this Partner and reselect partner, remove and readd invoice lines in this invoice!'))
            if any(line.price_unit == 0.0 for line in invoice.invoice_line_ids):
                raise ValidationError(_('You can not validate invoice with zero price unit invoice lines!'))

        return res

    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()
            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)

            name = inv.name or '/'
            if inv.payment_term_id:
                totlines = inv.with_context(ctx).payment_term_id.with_context(currency_id=inv.currency_id.id).compute(total, date_invoice)[0]
                res_amount_currency = total_currency
                ctx['date'] = date_invoice

                account_analytic_id = False
                if self.type in ('out_invoice', 'out_refund'):
                    sale = self.env['sale.order'].search([('name', '=', inv.origin)], limit=1)
                    if not sale:
                        analytic_default = self.env['account.analytic.default'].account_get(
                                                        False,
                                                        self.partner_id.id,
                                                        self._uid, time.strftime('%Y-%m-%d'),
                                                        company_id=self.env.user.company_id.id,
                                                        context=self._context)
                        if analytic_default:
                            account_analytic_id = analytic_default.analytic_id.id
                        else:
                            analytic_account = self.env['account.analytic.account'].search([('partner_id', '=', self.partner_id.id)], limit=1)
                            if analytic_account:
                                account_analytic_id = analytic_account.id
                    else:
                        account_analytic_id = inv.account_analytic_id.id

                else:
                    account_analytic_id = inv.account_analytic_id.id

                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id,
                        'account_analytic_id': account_analytic_id,
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id,
                    'account_analytic_id': account_analytic_id,
                })
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)
            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)
            date = inv.date or date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
                'memo': self.name,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['dont_create_taxes'] = True
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)

            # Temporary fix ...
            # TODO: its take from basking module due to its fix something for asset
            if inv.number:
                asset_ids = self.env['account.asset.asset'].sudo().search([('invoice_id', '=', inv.id), ('company_id', '=', inv.company_id.id)])
                if asset_ids:
                    asset_ids.write({'active': False})
            inv.invoice_line_ids.asset_create()
        return True

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        res = super(AccountInvoice, self)._prepare_refund(
                       invoice,
                       date_invoice=date_invoice,
                       date=date,
                       description=description,
                       journal_id=journal_id)
        res['account_analytic_id'] = invoice.account_analytic_id.id
        return res


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.model
    def default_get(self, fields):
        res = super(AccountInvoiceLine, self).default_get(fields)
        partner_id = self.env.context.get('partner_id', False)
        if partner_id:
            res['back_account_analytic_id'] = self._get_analytic_account_by_partner(partner_id)
        return res

    def _get_analytic_account_by_partner(self, partner_id):
        account_analytic_id = False
        if self._context.get('type') in ('out_invoice', 'out_refund') and partner_id:
            analytic_default = self.env['account.analytic.default'].account_get(
                                            False,
                                            partner_id,
                                            self._uid, time.strftime('%Y-%m-%d'),
                                            company_id=self.env.user.company_id.id,
                                            context=self._context)
            if analytic_default:
                account_analytic_id = analytic_default.analytic_id.id
        return account_analytic_id

    back_account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    asset_category_id = fields.Many2one('account.asset.category', string="Asset Category")

    @api.onchange('asset_category_id')
    def _onchange_asset_category_id(self):
        raise_warning = False
        if self.asset_category_id:
            if self.product_id:
                if self.invoice_id.type == 'out_invoice':
                    if self.asset_category_id != self.product_id.product_tmpl_id.deferred_revenue_category_id:
                        raise_warning = True
                elif self.invoice_id.type == 'in_invoice':
                    if self.asset_category_id != self.product_id.product_tmpl_id.asset_category_id:
                        raise_warning = True
        if raise_warning:
            warning_mess = {
                        'title': _('Different Asset Category!'),
                        'message' : _('You have select the asset category that is different from the category configured in product form.')
                            }
            return {'warning': warning_mess}
        return {}

    @api.model
    def create(self, vals):
        if vals.get('back_account_analytic_id'):
            vals.update({'account_analytic_id': vals['back_account_analytic_id']})
        return super(AccountInvoiceLine, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('back_account_analytic_id'):
            vals.update({'account_analytic_id': vals['back_account_analytic_id']})
        return super(AccountInvoiceLine, self).write(vals)


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    product_uom_id = fields.Many2one(index=True)
    so_line = fields.Many2one(index=True)


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        currency_id = self.env.user.company_id.currency_id
        if self.env.context.get('payment_via') == 'deposit':
            domain = ['|', ('currency_id', '=', False), ('currency_id', '=', currency_id.id)]
        if self.env.context.get('show_invoices'):
            if self.env.context.get('show_invoices') == 'base':
                domain = ['|', ('currency_id', '=', False), ('currency_id', '=', currency_id.id)]
            elif self.env.context.get('show_invoices') == 'foreign' and self.env.context.get('other_currency_id'):
                domain = [
                    '|', '|',
                    ('currency_id', '=', self.env.context['other_currency_id']),
                    ('currency_id', '=', False),
                    ('currency_id', '=', currency_id.id)
                ]
        return super(AccountJournal, self).name_search(name=name, args=args + domain, operator=operator, limit=limit)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    payment_via = fields.Selection([
                    ('normal', 'Normal'),
                    ('deposit', 'Deposit'),
                    ('bulk', 'Bulk Payment'),
                    ('adv_payment', 'Advance Payment')], string='Deposit')

    def _get_pair_to_reconcile(self):
        # field is either 'amount_residual' or 'amount_residual_currency' (if the reconciled account has a secondary currency set)
        field = self[0].account_id.currency_id and 'amount_residual_currency' or 'amount_residual'
        rounding = self[0].company_id.currency_id.rounding
        if self[0].currency_id and all([x.amount_currency and x.currency_id == self[0].currency_id for x in self]):
            # or if all lines share the same currency
            field = 'amount_residual_currency'
            rounding = self[0].currency_id.rounding
        if self._context.get('skip_full_reconcile_check') == 'amount_currency_excluded':
            field = 'amount_residual'
        elif self._context.get('skip_full_reconcile_check') == 'amount_currency_only':
            field = 'amount_residual_currency'
        # target the pair of move in self that are the oldest
        if self.env.context.get('from_bulk_payment'):
            sorted_moves = self
        else:
            sorted_moves = sorted(self, key=lambda a: a.date)

        debit = credit = False
        for aml in sorted_moves:
            if credit and debit:
                break
            if float_compare(aml[field], 0, precision_rounding=rounding) == 1 and not debit:
                debit = aml
            elif float_compare(aml[field], 0, precision_rounding=rounding) == -1 and not credit:
                credit = aml
        return debit, credit
