# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    active_in_general_payment = fields.Boolean('Active in General Payment')
    active_in_general_receipt = fields.Boolean('Active in General Receipt')

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        if self.env.context.get('from_general_payment'):
            currency_id = self.env.user.company_id.currency_id
            domain = ['|', ('currency_id', '=', False), ('currency_id', '=', currency_id.id)]
        return super(AccountJournal, self).name_search(name=name, args=args + domain, operator=operator, limit=limit)

    @api.onchange('type')
    def _onchange_type(self):
        if self.type not in ('bank', 'cash'):
            self.active_in_general_payment = False


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    payment_mode = fields.Selection([
                    ('cheque', 'Cheque'),
                    ('tt', 'TT'),
                    ('cash', 'Cash'),
                    ('credit', 'Credit Card'),
                    ('ba_hp_leasing', 'BA/HP/Leasing'),
                    ('other', 'Others')])
    # prevent duplicate tab issue (edit after post)
    @api.multi
    def write(self, vals):
        for rec in self:
            if not vals.get('state') and rec.state == 'posted':
                raise UserError('This payment is already posted!\n'
                                'Please discard the changes and refresh the page to see the latest update')
        return super(AccountVoucher, rec).write(vals)

    # prevent duplicate tab issue (validiate more than once)
    @api.multi
    def proforma_voucher(self):
        if self.state == 'posted':
            raise UserError('This payment is already posted!')
        return super(AccountVoucher, self).proforma_voucher()

    def _default_pay_now(self):
        # pay_now = 'pay_later'
        # if self.env.context.get('voucher_type') == 'purchase':
        pay_now = 'pay_now'
        return pay_now

    @api.model
    def _default_journal(self):
        return False

    journal_id = fields.Many2one(default=_default_journal)
    pay_now = fields.Selection(default=_default_pay_now)
    transfer_date = fields.Date('Transfer Date')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    cheque_no = fields.Char('Cheque No/Ref')
    name = fields.Char(size=30)

    @api.constrains('date', 'transfer_date')
    def _check_date(self):
        if (self.date and self.transfer_date) and (self.date < self.transfer_date):
            raise UserError(_('The Document Date cannot be later than the Payment Date'))

    @api.onchange('partner_id', 'pay_now')
    def onchange_partner_id(self):
        # if self.pay_now == 'pay_now':
        #     liq_journal = self.env['account.journal'].search([('type', 'in', ('bank', 'cash'))], limit=1)
        #     self.account_id = liq_journal.default_debit_account_id \
        #         if self.voucher_type == 'sale' else False
        # else:
        #     if self.partner_id:
        #         self.account_id = self.partner_id.property_account_receivable_id \
        #             if self.voucher_type == 'sale' else False
        #     else:
        #         self.account_id = self.journal_id.default_debit_account_id \
        #             if self.voucher_type == 'sale' else False
        self.account_id = False

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        account_id = False
        if self.journal_id and self.env.context.get('voucher_type') == 'purchase':
            account_id = self.journal_id.default_credit_account_id
        else:
            account_id = self.journal_id.default_debit_account_id
        self.account_id = account_id

    @api.multi
    def account_move_get(self):
        result = super(AccountVoucher, self).account_move_get()
        result['memo'] = self.name
        return result

    @api.multi
    def first_move_line_get(self, move_id, company_currency, current_currency):
        debit = credit = 0.0
        if self.voucher_type == 'purchase':
            credit = self._convert_amount(self.amount)
        elif self.voucher_type == 'sale':
            debit = self._convert_amount(self.amount)
        if debit < 0.0: debit = 0.0
        if credit < 0.0: credit = 0.0
        sign = debit - credit < 0 and -1 or 1
        # set the first line of the voucher
        move_line = {
            'name': self.number or '/',
            'debit': debit,
            'credit': credit,
            'account_id': self.account_id.id,
            'move_id': move_id,
            'journal_id': self.journal_id.id,
            'partner_id': self.partner_id.id,
            'currency_id': company_currency != current_currency and current_currency or False,
            'amount_currency': (sign * abs(self.amount)  # amount < 0 for refunds
                if company_currency != current_currency else 0.0),
            'date': self.date,
            'date_maturity': self.date_due,
            'analytic_account_id': self.analytic_account_id.id,
        }
        return move_line

    @api.multi
    def voucher_move_line_create(self, line_total, move_id, company_currency, current_currency):
        for line in self.line_ids:
            #create one move line per voucher line where amount is not 0.0
            if not line.price_subtotal:
                continue
            # convert the amount set on the voucher line into the currency of the voucher's company
            # this calls res_curreny.compute() with the right context, so that it will take either the rate on the voucher if it is relevant or will use the default behaviour
            amount = self._convert_amount(line.price_unit*line.quantity)
            move_line = {
                'journal_id': self.journal_id.id,
                'name': self.number or '/',
                'account_id': line.account_id.id,
                'move_id': move_id,
                'partner_id': self.partner_id.id,
                'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                'quantity': 1,
                'credit': abs(amount) if self.voucher_type == 'sale' else 0.0,
                'debit': abs(amount) if self.voucher_type == 'purchase' else 0.0,
                'date': self.date,
                'tax_ids': [(4, t.id) for t in line.tax_ids],
                'amount_currency': line.price_subtotal if current_currency != company_currency else 0.0,
            }
            # TODO: Commented this code due to BASKIN- 93
            # voucher_pur_name = ''
            # if self.voucher_type == 'purchase':
            #     voucher_pur_name = self.number or '/'
            # self.env['account.move.line'].with_context(voucher_pur_name=voucher_pur_name).create(move_line)
            self.env['account.move.line'].create(move_line)
        return line_total

    @api.multi
    def action_move_line_create(self):
        '''
        Confirm the vouchers given in ids and create the journal entries for each of them
        '''
        for voucher in self:
            local_context = dict(self._context, force_company=voucher.journal_id.company_id.id)
            if voucher.move_id:
                continue
            company_currency = voucher.journal_id.company_id.currency_id.id
            current_currency = voucher.currency_id.id or company_currency
            # we select the context to use accordingly if it's a multicurrency case or not
            # But for the operations made by _convert_amount, we always need to give the date in the context
            ctx = local_context.copy()
            ctx['date'] = voucher.date
            ctx['check_move_validity'] = False
            # Create the account move record.
            move = self.env['account.move'].create(voucher.account_move_get())
            # Get the name of the account_move just created
            # Create the first line of the voucher
            move_line = self.env['account.move.line'].with_context(ctx).create(voucher.with_context(ctx).first_move_line_get(move.id, company_currency, current_currency))
            line_total = move_line.debit - move_line.credit
            if voucher.voucher_type == 'sale':
                line_total = line_total - voucher._convert_amount(voucher.tax_amount)
            elif voucher.voucher_type == 'purchase':
                line_total = line_total + voucher._convert_amount(voucher.tax_amount)
            # Create one move line per voucher line where amount is not 0.0
            line_total = voucher.with_context(ctx).voucher_move_line_create(line_total, move.id, company_currency, current_currency)

            # Add tax correction to move line if any tax correction specified
            if voucher.tax_correction != 0.0:
                tax_move_line = self.env['account.move.line'].search([('move_id', '=', move.id), ('tax_line_id', '!=', False)], limit=1)
                if len(tax_move_line):
                    tax_move_line.write({
                        'debit': tax_move_line.debit + voucher.tax_correction if tax_move_line.debit > 0 else 0,
                        'credit': tax_move_line.credit + voucher.tax_correction if tax_move_line.credit > 0 else 0
                    })
            number = '/'
            if voucher.voucher_type == 'purchase':
                sequence = self.env['ir.sequence'].search([
                    ('code', 'in', ('general.payment.gssb', 'general.payment.mssb')),
                    ('company_id', '=', self.env.user.company_id.id)
                ], limit=1)

                # sequence_code = sequence.code
                number = self.env['ir.sequence'].next_by_code(sequence.code) or '/'
                # if self.env.user.company_id.name.startswith('Golden Scoop'):
                #     number = self.env['ir.sequence'].next_by_code('general.payment.gssb') or '/'
                # elif self.env.user.company_id.name.startswith('Mega Scoop'):
                #     number = self.env['ir.sequence'].next_by_code('general.payment.mssb') or '/'
            else:
                number = move.name

            # We post the voucher.
            voucher.write({
                'move_id': move.id,
                'state': 'posted',
                'number': number
            })
            voucher.line_ids.write({'name': number})
            # transfer number in to move line of general payment
            voucher.move_id.line_ids.write({'name': number})
            move.post()
        return True


class AccountVoucherLine(models.Model):
    _inherit = 'account.voucher.line'

    name = fields.Text(default='/', readonly=True)
    backend_name = fields.Text('Description Backend', default='/')

    @api.multi
    def product_id_change(self, product_id, partner_id=False, price_unit=False, company_id=None, currency_id=None, type=None):
        context = self._context
        company_id = company_id if company_id is not None else context.get('company_id', False)
        company = self.env['res.company'].browse(company_id)
        currency = self.env['res.currency'].browse(currency_id)
        if not partner_id and type != 'purchase':
            raise UserError(_("You must first select a partner!"))
        part = self.env['res.partner'].browse(partner_id)
        if part.lang:
            self = self.with_context(lang=part.lang)

        product = self.env['product.product'].browse(product_id)
        fpos = part.property_account_position_id
        account = self._get_account(product, fpos, type)
        values = {
            'name': product.partner_ref or '/',
            'backend_name': product.partner_ref or '/',
            'account_id': account.id,
        }

        if type == 'purchase':
            values['price_unit'] = price_unit or product.standard_price
            taxes = product.supplier_taxes_id or account.tax_ids
            if product.description_purchase:
                values['name'] += '\n' + product.description_purchase
        else:
            values['price_unit'] = price_unit or product.lst_price
            taxes = product.taxes_id or account.tax_ids
            if product.description_sale:
                values['name'] += '\n' + product.description_sale

        values['tax_ids'] = taxes.ids

        if company and currency:
            if company.currency_id != currency:
                if type == 'purchase':
                    values['price_unit'] = price_unit or product.standard_price
                values['price_unit'] = values['price_unit'] * currency.rate

        return {'value': values, 'domain': {}}

    @api.model
    def create(self, vals):
        if vals.get('backend_name'):
            vals['name'] = vals['backend_name']
        return super(AccountVoucherLine, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('backend_name'):
            vals['name'] = vals['backend_name']
        return super(AccountVoucherLine, self).write(vals)


# class account_move_line(models.Model):
#     _inherit = 'account.move.line'

#     @api.model
#     def create(self, vals):
#         if self.env.context.get('voucher_type') == 'purchase' and self.env.context.get('voucher_pur_name'):
#             vals['name'] = self.env.context['voucher_pur_name']
#         return super(account_move_line, self).create(vals)
