from openerp import models, fields, api, SUPERUSER_ID, _
from openerp.exceptions import UserError, RedirectWarning, ValidationError
from openerp.exceptions import except_orm

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
}

class br_account(models.Model):
    _inherit = 'account.tax'

    #fix T4443
    @api.multi
    def unlink(self):
        company_id = self.env.user.company_id.id
        ir_values = self.env['ir.values']
        if ir_values.get_default('product.template', 'supplier_taxes_id', company_id=company_id) is not None:
            supplier_taxes_id = set(ir_values.get_default('product.template', 'supplier_taxes_id', company_id=company_id))
            deleted_sup_tax = self.filtered(lambda tax: tax.id in supplier_taxes_id)
            if deleted_sup_tax:
                ir_values.sudo().set_default('product.template', "supplier_taxes_id", list(supplier_taxes_id - set(deleted_sup_tax.ids)), for_all_users=True, company_id=company_id)
            taxes_id = set(self.env['ir.values'].get_default('product.template', 'taxes_id', company_id=company_id))
            deleted_tax = self.filtered(lambda tax: tax.id in taxes_id)
            if deleted_tax:
                ir_values.sudo().set_default('product.template', "taxes_id", list(taxes_id - set(deleted_tax.ids)), for_all_users=True, company_id=company_id)

class br_AcountPayment(models.Model):
    _inherit = 'account.payment'
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')], track_visibility='always')

    @api.model
    def default_get(self, fields):
        rec = super(br_AcountPayment, self).default_get(fields)
        invoice_defaults = self.resolve_2many_commands('invoice_ids', rec.get('invoice_ids'))
        if invoice_defaults and len(invoice_defaults) == 1:
            invoice = invoice_defaults[0]
            rec['communication'] = invoice['reference'] or invoice['name'] or invoice['number']
            rec['currency_id'] = invoice['currency_id'][0]
            rec['payment_type'] = invoice['type'] in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
            rec['partner_type'] = MAP_INVOICE_TYPE_PARTNER_TYPE[invoice['type']]
            rec['partner_id'] = invoice['partner_id'][0]
            rec['amount'] = invoice['residual']
            #vannh get analytic account from SO or PO
            origin = invoice['origin']
            account_analytic_ids = []
            origin_so = self.env['sale.order'].search([('name', '=', origin)], limit=1)
            if origin_so and origin_so.project_id:
                account_analytic_ids.append(origin_so.project_id.id)
            for inv_line in invoice['invoice_line_ids']:
                inv_line_obj = self.env['account.invoice.line'].browse(inv_line)
                if inv_line_obj.account_analytic_id:
                    account_analytic_ids.append(inv_line_obj.account_analytic_id.id)
            ret_analytic_ids = set(account_analytic_ids)

            if ret_analytic_ids:
                rec['account_analytic_id'] = list(ret_analytic_ids)[0]
                # rec['domain'] = {'account_analytic_id': [('id', 'in', list(ret_analytic_ids))]}
        return rec

    def _get_shared_move_line_vals(self, debit, credit, amount_currency, move_id, invoice_id=False):
        """ override function _get_share_move_line_vals
        """
        #  In case we get account_analytic_id from elsewhere
        account_analytic_id = self.env.context.get('account_analytic_id', False)
        if not account_analytic_id and self.account_analytic_id:
            account_analytic_id = self.account_analytic_id.id
        return {
            'partner_id': self.payment_type in ('inbound', 'outbound') and self.env['res.partner']._find_accounting_partner(self.partner_id).id or False,
            'invoice_id': invoice_id and invoice_id.id or False,
            'move_id': move_id,
            'debit': debit,
            'credit': credit,
            'amount_currency': amount_currency or False,
            'analytic_account_id': account_analytic_id,
        }

    @api.model
    def _create_payment_entry(self, amount):
        """ override function _create_payment_entry
        """
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        invoice_currency = False
        if self.invoice_ids and all([x.currency_id == self.invoice_ids[0].currency_id for x in self.invoice_ids]):
            #if all the invoices selected share the same currency, record the paiement in that currency too
            invoice_currency = self.invoice_ids[0].currency_id
        debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(amount, self.currency_id, self.company_id.currency_id, invoice_currency)

        move = self.env['account.move'].create(self._get_move_vals())

        #Write line corresponding to invoice payment
        my_context = self.env.context.copy()
        my_context.update(account_analytic_id=self.account_analytic_id.id if self.account_analytic_id else False)
        counterpart_aml_dict = self.with_context(my_context)._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
        counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
        counterpart_aml_dict.update({'currency_id': currency_id})
        counterpart_aml = aml_obj.create(counterpart_aml_dict)

        #Reconcile with the invoices
        if self.payment_difference_handling == 'reconcile' and self.payment_difference:
            my_context = self.env.context.copy()
            my_context.update(account_analytic_id=self.account_analytic_id.id if self.account_analytic_id else False)
            writeoff_line = self.with_context(my_context)._get_shared_move_line_vals(0, 0, 0, move.id, False)
            debit_wo, credit_wo, amount_currency_wo, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(self.payment_difference, self.currency_id, self.company_id.currency_id, invoice_currency)
            writeoff_line['name'] = _('Write-Off')
            writeoff_line['account_id'] = self.writeoff_account_id.id
            writeoff_line['debit'] = debit_wo
            writeoff_line['credit'] = credit_wo
            writeoff_line['amount_currency'] = amount_currency_wo
            writeoff_line['currency_id'] = currency_id
            # Longdt: Add analytic account to writeoff_line
            writeoff_line['analytic_account_id'] = self.account_analytic_id and self.account_analytic_id.id or False
            writeoff_line = aml_obj.create(writeoff_line)
            if counterpart_aml['debit']:
                counterpart_aml['debit'] += credit_wo - debit_wo
            if counterpart_aml['credit']:
                counterpart_aml['credit'] += debit_wo - credit_wo
            counterpart_aml['amount_currency'] -= amount_currency_wo
        new_ctx = self.env.context.copy()
        new_ctx.update(analytic_account_id=self.account_analytic_id and self.account_analytic_id.id or False)
        self.with_context(new_ctx).invoice_ids.register_payment(counterpart_aml)

        #Write counterpart lines
        if not self.currency_id != self.company_id.currency_id:
            amount_currency = 0
        my_context = self.env.context.copy()
        my_context.update(account_analytic_id=self.account_analytic_id.id if self.account_analytic_id else False)
        liquidity_aml_dict = self.with_context(my_context)._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
        liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
        aml_obj.create(liquidity_aml_dict)

        move.post()
        return move


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def create_exchange_rate_entry(self, aml_to_fix, amount_diff, diff_in_currency, currency, move_date):
        """ Overridden funciton, check origin in account/account.py
        """
        for rec in self:
            if not rec.company_id.currency_exchange_journal_id:
                raise UserError(_("You should configure the 'Exchange Rate Journal' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            if not self.company_id.income_currency_exchange_account_id.id:
                raise UserError(_("You should configure the 'Gain Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            if not self.company_id.expense_currency_exchange_account_id.id:
                raise UserError(_("You should configure the 'Loss Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            move_vals = {'journal_id': rec.company_id.currency_exchange_journal_id.id, 'rate_diff_partial_rec_id': rec.id}

            # The move date should be the maximum date between payment and invoice (in case
            # of payment in advance). However, we should make sure the move date is not
            # recorded after the end of year closing.
            if move_date > rec.company_id.fiscalyear_lock_date:
                move_vals['date'] = move_date
            move = rec.env['account.move'].create(move_vals)
            amount_diff = rec.company_id.currency_id.round(amount_diff)
            diff_in_currency = currency.round(diff_in_currency)
            line_to_reconcile = rec.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': _('Currency exchange rate difference'),
                'debit': amount_diff < 0 and -amount_diff or 0.0,
                'credit': amount_diff > 0 and amount_diff or 0.0,
                'account_id': rec.debit_move_id.account_id.id,
                'move_id': move.id,
                'currency_id': currency.id,
                'amount_currency': -diff_in_currency,
                'partner_id': rec.debit_move_id.partner_id.id,
                #Longdt: add analytic_account_id
                'analytic_account_id': self.env.context['analytic_account_id']
            })
            rec.env['account.move.line'].create({
                'name': _('Currency exchange rate difference'),
                'debit': amount_diff > 0 and amount_diff or 0.0,
                'credit': amount_diff < 0 and -amount_diff or 0.0,
                'account_id': amount_diff > 0 and rec.company_id.currency_exchange_journal_id.default_debit_account_id.id or rec.company_id.currency_exchange_journal_id.default_credit_account_id.id,
                'move_id': move.id,
                'currency_id': currency.id,
                'amount_currency': diff_in_currency,
                'partner_id': rec.debit_move_id.partner_id.id,
                #Longdt: add analytic_account_id
                'analytic_account_id': self.env.context['analytic_account_id']
            })
            for aml in aml_to_fix:
                partial_rec = rec.env['account.partial.reconcile'].create({
                    'debit_move_id': aml.credit and line_to_reconcile.id or aml.id,
                    'credit_move_id': aml.debit and line_to_reconcile.id or aml.id,
                    'amount': abs(aml.amount_residual),
                    'amount_currency': abs(aml.amount_residual_currency),
                    'currency_id': currency.id,
                })
            move.post()
        return line_to_reconcile.id, partial_rec.id


class br_account_account(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def compute_invoice_totals(self, company_currency, invoice_move_lines):
        total = 0
        total_currency = 0
        for line in invoice_move_lines:
            if self.currency_id != company_currency:
                currency = self.currency_id.with_context(date=self.date_invoice or fields.Date.context_today(self))
                line['currency_id'] = currency.id
                line['amount_currency'] = currency.round(line['price'])
                line['price'] = currency.compute(line['price'], company_currency)
            else:
                line['currency_id'] = False
                line['amount_currency'] = False
                line['price'] = self.currency_id.round(line['price'])
            if self.type in ('out_invoice', 'in_refund'):
                total += line['price']
                total_currency += line['amount_currency'] or line['price']
                line['price'] = - line['price']
            else:
                total -= line['price']
                total_currency -= line['amount_currency'] or line['price']
        return total, total_currency, invoice_move_lines

    # FIXME:  Override this function also affects another module (account_asset_infoice.py), please consider another way to split invoice line, e.g: split after created lines ...
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
            company_currency = inv.company_id.currency_id
            if not inv.date_invoice:
                if inv.currency_id != company_currency and inv.tax_line_ids:
                    raise except_orm(
                        _('Warning!'),
                        _('No invoice date!'
                          '\nThe invoice currency is not the same than the company currency.'
                          'An invoice date is required to determine the exchange rate to apply. '
                          'Do not forget to update the taxes!')
                        )
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = inv.invoice_line_move_line_get()
            line_tax = inv.tax_line_move_line_get() #vannh tach receivale account
            iml += line_tax

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount

            tmp_analytic_acc_ids = [x['account_analytic_id'] for x in iml if 'account_analytic_id' in x]
            ls_analytic_acc_ids = set(tmp_analytic_acc_ids)
            #vannh tach receiveable theo analytic account
            for i_tax in list(ls_analytic_acc_ids):
                analytic_account = i_tax
                alt_iml = [x for x in iml if 'account_analytic_id' in x and x['account_analytic_id'] == analytic_account]

                total, total_currency, alt_iml = inv.with_context(ctx).compute_invoice_totals(company_currency, alt_iml)

                name = inv.name or '/'
                if inv.payment_term_id:
                    totlines = \
                    inv.with_context(ctx).payment_term_id.with_context(currency_id=inv.currency_id.id).compute(total,
                                                                                                               date_invoice)[
                        0]
                    res_amount_currency = total_currency
                    ctx['date'] = date_invoice
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
                            'account_analytic_id': analytic_account or False
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
                        'account_analytic_id': analytic_account or False
                    })
            # end vannh

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

            if inv.number:
                asset_ids = self.env['account.asset.asset'].sudo().search([('invoice_id', '=', inv.id), ('company_id', '=', inv.company_id.id)])
                if asset_ids:
                    asset_ids.write({'active': False})
            inv.invoice_line_ids.asset_create()
        return True
