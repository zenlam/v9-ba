# -*- coding: utf-8 -*-

from lxml import etree

from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError
import openerp.addons.decimal_precision as dp
from openerp.tools.float_utils import float_round


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    rate = fields.Float(digits=(12, 12))

    def _get_conversion_rate(self, cr, uid, from_currency, to_currency, context=None):
        res = super(ResCurrency, self)._get_conversion_rate(cr, uid, from_currency, to_currency, context=context)
        if context.get('bulk_payment_currency_rate'):
            res = context['bulk_payment_currency_rate']
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        if self.env.context.get('from_other_currency'):
            return self.search(args + [('id', '!=', self.env.user.company_id.currency_id.id)], limit=limit).name_get()
        return super(ResCurrency, self).name_search(name, args=args, operator=operator, limit=limit)


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    rate = fields.Float(digits=(12, 12))


class AccountBulkPayment(models.Model):
    _name = "account.payment"
    _inherit = ['account.payment', 'mail.thread']

    @api.multi
    def write(self, vals):
        for rec in self:
            if not vals.get('state') and rec.state == 'posted':
                raise UserError('This payment is already posted!\n'
                                'Please discard the changes and refresh the page to see the latest update')
        return super(AccountBulkPayment, rec).write(vals)

    @api.depends('other_currency_id', 'currency_id', 'show_invoices')
    def _compute_show(self):
        for payment in self:
            payment.show_other_currency = False
            if payment.other_currency_id == payment.currency_id and payment.show_invoices == 'foreign':
                payment.show_other_currency = False
            elif payment.other_currency_id != payment.currency_id and payment.show_invoices == 'foreign':
                payment.show_other_currency = True

    @api.depends('other_currency_id', 'currency_id', 'amount', 'other_currency_paid_amount', 'direct_exchange_rate', 'journal_id')
    def _get_curreny_rate(self):
        for rec in self:
            currency_rate = ''
            if rec.direct_exchange_rate:
                currency_rate = '1 ' + str(rec.other_currency_id.name) + ' = ' + str(rec.direct_exchange_rate) + ' ' + str(rec.company_id.currency_id.name)
            rec.conversion_rate = currency_rate

    bulk_payment = fields.Boolean('Bulk Payment')
    amount = fields.Float(digits=0, track_visibility='always')
    line_ids = fields.One2many(
                    'account.bulk.payment.line',
                    'payment_id',
                    'Payment Lines',
                    readonly=True, copy=True,
                    states={'draft': [('readonly', False)]})
    line_cr_ids = fields.One2many(
                    'account.bulk.payment.line',
                    'payment_id',
                    'Credits',
                    domain=[('type', '=', 'cr')],
                    context={'default_type': 'cr'},
                    readonly=True,
                    states={'draft': [('readonly', False)]})
    line_dr_ids = fields.One2many(
                    'account.bulk.payment.line',
                    'payment_id',
                    'Debits',
                    domain=[('type', '=', 'dr')],
                    context={'default_type': 'dr'},
                    readonly=True,
                    states={'draft': [('readonly', False)]})
    show_invoices = fields.Selection([
                        ('base', 'Base Currency'),
                        ('foreign', 'Foreign Currency')],
                        string='Invoices Types',
                        default='base',
                        readonly=True,
                        states={'draft': [('readonly', False)]}, track_visibility='always')
    other_currency_id = fields.Many2one('res.currency', string='Other Currency', readonly=True, states={'draft': [('readonly', False)]}, track_visibility='always')
    other_currency_paid_amount = fields.Float(
                                    'Currency Paid Amount',
                                    readonly=True,
                                    states={'draft': [('readonly', False)]}, track_visibility='always')
    exchange_rate = fields.Float(
                        'Odoo Base Exchange Rate',
                        digits=dp.get_precision('Currency Rate'),
                        readonly=True,
                        states={'draft': [('readonly', False)]}, track_visibility='always')
    direct_exchange_rate = fields.Float(
                            'Direct Exchange Rate',
                            digits=dp.get_precision('Currency Rate'),
                            readonly=True,
                            states={'draft': [('readonly', False)]}, track_visibility='always')
    show_other_currency = fields.Boolean(compute='_compute_show', string='Show Currency')
    is_same_currency = fields.Boolean(string='Is Same Currency?')
    conversion_rate = fields.Char(compute='_get_curreny_rate', string='Conversion Rate', track_visibility='always')
    creator_remarks = fields.Text('Creator Remarks', readonly=True, states={'draft': [('readonly', False)]}, track_visibility='always')
    authorizer_remarks = fields.Text('Authorizer Remarks', readonly=True, states={'draft': [('readonly', False)]}, track_visibility='always')
    state = fields.Selection(selection_add=[('cancel', 'Cancelled')], track_visibility='onchange')
    payment_via = fields.Selection(selection='_get_payment_via',
                                   string='Deposit', default='normal', track_visibility='always',
                                   readonly=True, states={'draft': [('readonly', False)]})
    memo = fields.Char('Memo', size=30, track_visibility='always',)
    cheque_no = fields.Char('Cheque No / Ref', track_visibility='always',)
    payment_mode = fields.Selection([
                        ('cheque', 'Cheque'),
                        ('tt', 'TT'),
                        ('cash', 'Cash'),
                        ('credit', 'Credit'),
                        ('ba_hp_leasing', 'BA/HP/Leasing'),
                        ('other', 'Others')], string='Payment Mode', track_visibility='onchange',)
    move_id = fields.Many2one('account.move', string='Journal Entry', copy=False, track_visibility='always')
    move_ids = fields.Many2many(
                    'account.move',
                    'account_move_payment_rel',
                    'payment_id',
                    'move_id',
                    string='Journal Entries',
                    copy=False)
    partner_type = fields.Selection(selection='_get_partner_type', track_visibility='always')
    account_analytic_id = fields.Many2one(track_visibility='always')
    payment_date = fields.Date(track_visibility='always')

    @api.one
    @api.constrains('amount')
    def _check_amount(self):
        return False
        # if not self.amount > 0.0:
        #     raise ValidationError('The payment amount must be strictly positive.')

    @api.onchange('partner_type')
    def _onchange_partner_type(self):
        # Set partner_id domain
        if self.partner_type:
            return {'domain': {'partner_id': [(self.partner_type, '=', True), ('company_type', '=', 'company')]}}

    @api.onchange('show_invoices')
    def _onchange_show_invoices(self):
        if self.show_invoices == 'base':
            self.other_currency_id = False

    def _check_paid_amount(self):
        currency_id = self.currency_id
        other_currency_id = self.other_currency_id
        for rec in self:
            if rec.bulk_payment and rec.payment_type == 'inbound' and not self.env.context.get('from_refresh'):
                line_total = float_round(sum([x.amount for x in rec.line_cr_ids]), precision_digits=currency_id.decimal_places)
                line_foreign_total = float_round(sum([x.amount_foregin for x in rec.line_cr_ids]), precision_digits=other_currency_id.decimal_places)
                main_amount = float_round(rec.amount, precision_digits=currency_id.decimal_places)
                main_foreign_amount = float_round(rec.other_currency_paid_amount, precision_digits=other_currency_id.decimal_places)
                if rec.show_invoices == 'base' and main_amount != line_total:
                    raise ValidationError(_('The sum of \'Payment Amount(Base)\' is not equal to \'Payment Amount\' !'))
                if rec.show_invoices == 'foreign':
                    if rec.other_currency_id != rec.currency_id and (main_foreign_amount != line_foreign_total or main_amount != line_total):
                        raise ValidationError(_('The sum of \'Payment Amount(Foreign)\' is not equal to \'Currency Paid Amount \' or \'Payment Amount(Base)\' is not equal to \'Payment Amount\' !'))
                    if rec.other_currency_id == rec.currency_id and rec.amount != line_foreign_total:
                        raise ValidationError(_('The sum of \'Payment Amount(Foreign)\' is not equal to \'Currency Paid Amount \' amount !'))
            elif rec.bulk_payment and rec.payment_type == 'outbound' and not self.env.context.get('from_refresh'):
                line_total = float_round(sum([x.amount for x in rec.line_dr_ids]), precision_digits=currency_id.decimal_places)
                line_foreign_total = float_round(sum([x.amount_foregin for x in rec.line_dr_ids]), precision_digits=other_currency_id.decimal_places)
                main_amount = float_round(rec.amount, precision_digits=currency_id.decimal_places)
                main_foreign_amount = float_round(rec.other_currency_paid_amount, precision_digits=other_currency_id.decimal_places)
                if rec.show_invoices == 'base' and main_amount != line_total:
                    raise ValidationError(_('The sum of \'Payment Amount(Base)\' is not equal to \'Payment Amount\' !'))
                if rec.show_invoices == 'foreign':
                    if rec.other_currency_id != rec.currency_id and (main_foreign_amount != line_foreign_total or main_amount != line_total):
                        raise ValidationError(_('The sum of \'Payment Amount(Foreign)\' is not equal to \'Currency Paid Amount \' or \'Payment Amount(Base)\' is not equal to \'Payment Amount\' !'))
                    if rec.other_currency_id == rec.currency_id and main_amount != line_foreign_total:
                        raise ValidationError(_('The sum of \'Payment Amount(Foreign)\' is not equal to \'Currency Paid Amount \' amount !'))

    def _get_payment_via(self):
        context = self._context
        if 'no_normal_bulk' in context and context['no_normal_bulk']:
            return [('deposit', 'Deposit'),
                    ('adv_payment', 'Advance Payment')]
        else:
            return [('normal', 'Normal'),
                    ('deposit', 'Deposit'),
                    ('bulk', 'Bulk Payment'),
                    ('adv_payment', 'Advance Payment')]

    def _get_partner_type(self):
        context = self._context
        if 'default_payment_type' in context:
            if context['default_payment_type'] == 'inbound':
                return [('customer', 'Customer')]
            elif context['default_payment_type'] == 'outbound':
                return [('supplier', 'Vendor')]
        return [('customer', 'Customer'), ('supplier', 'Vendor')]

    # @api.model
    # def create(self, vals):
    #     res = super(AccountBulkPayment, self).create(vals)
    #     res._check_paid_amount()
    #     return res

    # @api.multi
    # def write(self, vals):
    #     res = super(AccountBulkPayment, self).write(vals)
    #     for payment in self:
    #         payment._check_paid_amount()
    #     return res

    def _check_before_validate(self):
        currency_id = self.env.user.company_id.currency_id
        for rec in self:
            if rec.payment_type == 'inbound' and rec.show_invoices == 'base':
                if any(abs(float_round(line.move_line_id.amount_residual, precision_digits=currency_id.decimal_places)) != float_round(
                    line.amount_unreconciled, precision_digits=currency_id.decimal_places) and line.amount_unreconciled > 0.0 for line in rec.line_cr_ids):
                    raise ValidationError(_('You need to click first Reload Button before validate entry!'))
            elif rec.payment_type == 'outbound' and rec.show_invoices == 'base':
                if any(abs(float_round(line.move_line_id.amount_residual, precision_digits=currency_id.decimal_places)) != float_round(
                    line.amount_unreconciled, precision_digits=currency_id.decimal_places) and  line.amount_unreconciled > 0.0 for line in rec.line_dr_ids):
                    raise ValidationError(_('You need to click first Reload Button before validate entry!'))
        return True

    def _get_move_vals(self, journal=None):
        result = super(AccountBulkPayment, self)._get_move_vals(journal=journal)
        result['memo'] = self.memo
        return result

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(AccountBulkPayment, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        ctx = self.env.context
        if view_type == 'form' and self.env.context.get('default_bulk_payment'):
            doc = etree.XML(res['arch'])
            for sheet in doc.xpath("//sheet"):
                parent = sheet.getparent()
                index = parent.index(sheet)
                for child in sheet:
                    parent.insert(index, child)
                    index += 1
                parent.remove(sheet)
            res['arch'] = etree.tostring(doc)
            doc = etree.XML(res['arch'])

        # if self.env.context.get('default_payment_via') != 'bulk' or ctx.get('default_payment_via') == 'bulk' \
        #         and ctx.get('default_payment_type') != 'outbound':
        #     reports = []
        #     if res.get('toolbar', False) and res.get('toolbar').get('print', False):
        #         reports = res.get('toolbar').get('print')
        #         new_reports = list(reports)
        #         for report in new_reports:
        #             if report.get('report_name') == 'baskin_bulk_payment.report_baskin_vendor_payment_foreign':
        #                 res['toolbar']['print'].remove(report)
        #             if report.get('report_name') == 'baskin_bulk_payment.report_baskin_vendor_payment_base':
        #                 res['toolbar']['print'].remove(report)
        #
        # if ctx.get('default_payment_via') != 'deposit' or ctx.get('default_payment_via') == 'deposit' \
        #         and ctx.get('default_payment_type') != 'outbound':
        #     if res.get('toolbar', False) and res.get('toolbar').get('print', False):
        #         reports = res.get('toolbar').get('print')
        #         for report in reports:
        #             if report.get('report_name') == 'baskin_bulk_payment.report_baskin_vendor_deposit':
        #                 res['toolbar']['print'].remove(report)

        pay_in = ['baskin_bulk_payment.report_baskin_cust_payment_foreign',
                  'baskin_bulk_payment.report_baskin_cust_payment_base']
        pay_out = ['baskin_bulk_payment.report_baskin_vendor_payment_foreign',
                   'baskin_bulk_payment.report_baskin_vendor_payment_base']
        depo_in = ['baskin_bulk_payment.report_baskin_customer_deposit']
        depo_out = ['baskin_bulk_payment.report_baskin_vendor_deposit']

        if res.get('toolbar', False) and res.get('toolbar').get('print', False):
            reports = res.get('toolbar').get('print')
            for report in list(reports):
                if ctx.get('default_payment_via') == 'bulk' and ctx.get('default_payment_type') == 'inbound':
                    if report.get('report_name') not in pay_in:
                        res['toolbar']['print'].remove(report)
                elif ctx.get('default_payment_via') == 'bulk' and ctx.get('default_payment_type') == 'outbound':
                    if report.get('report_name') not in pay_out:
                        res['toolbar']['print'].remove(report)
                elif ctx.get('default_payment_via') == 'deposit' and ctx.get('default_payment_type') == 'inbound':
                    if report.get('report_name') not in depo_in:
                        res['toolbar']['print'].remove(report)
                elif ctx.get('default_payment_via') == 'deposit' and ctx.get('default_payment_type') == 'outbound':
                    if report.get('report_name') not in depo_out:
                        res['toolbar']['print'].remove(report)
        return res

    @api.onchange('amount', 'other_currency_paid_amount')
    def _onchange_exchange_rate(self):
        if self.show_invoices == 'foreign' and self.other_currency_id and self.other_currency_id != self.currency_id:
            if self.other_currency_paid_amount != 0.0 and self.amount != 0.0:
                exchange_amount = self.other_currency_paid_amount / self.amount
#                self.exchange_rate = exchange_amount
                self.direct_exchange_rate = 1 / exchange_amount

    @api.onchange('currency_id', 'other_currency_id')
    def _onchange_curerncy(self):
        self.is_same_currency = False
        if not self.other_currency_id or self.currency_id == self.other_currency_id:
            self.is_same_currency = True

    @api.onchange('payment_date', 'other_currency_id')
    def _onchange_payment_date(self):
        if self.payment_date and self.other_currency_id:
            other_currency = self.other_currency_id.with_context(date=self.payment_date)
            self.exchange_rate = other_currency.rate
            self.direct_exchange_rate = other_currency.direct_rate

    @api.onchange('amount', 'other_currency_paid_amount', 'direct_exchange_rate')
    def _onchange_direrct_exchange_rate(self):
        if self.show_invoices == 'foreign' and self.direct_exchange_rate:
            if self.partner_type == 'supplier':
                for line in self.line_dr_ids:
                    line.payment_direct_rate = self.direct_exchange_rate
                    line.amount = line.amount_foregin * self.direct_exchange_rate
                    line.diff_rate = self.exchange_rate - line.invoice_rate
                    line.diff_direct_rate = self.direct_exchange_rate - line.invoice_direct_rate

            elif self.partner_type == 'customer':
                for line in self.line_cr_ids:
                    line.payment_direct_rate = self.direct_exchange_rate
                    line.amount = line.amount_foregin * self.direct_exchange_rate
                    line.diff_rate = self.exchange_rate - line.invoice_rate
                    line.diff_direct_rate = self.direct_exchange_rate - line.invoice_direct_rate

    @api.onchange('partner_id', 'partner_type', 'currency_id', 'other_currency_id', 'show_invoices', 'exchange_rate')
    def _onchange_partner(self):
        self.line_ids = False
        self.line_cr_ids = False
        self.line_dr_ids = False

    @api.multi
    def button_reload(self):
        account_move_lines = self.env['account.move.line']
        ResCurrency = self.env['res.currency']
        for bulk in self:
            bulk.line_ids.unlink()
            company_currency = self.env.user.company_id.currency_id
            currency_id = self.env.user.company_id.currency_id
            other_currency_id = self.other_currency_id
            journal_types = ['sale', 'purchase', 'general', 'opening']

            sql_journal_string = 'ajor.type IN ' + str(journal_types).replace('[', '(').replace(']', ')')

            if bulk.bulk_payment:
                search_currency_ids = []
                if bulk.show_invoices == 'base':
                    search_currency_ids.append(False)
                    search_currency_ids.append(currency_id.id)
                    sql_currency_string = 'rcur.id IS NULL'
                else:
                    search_currency_ids.append(bulk.other_currency_id.id)
                    sql_currency_string = 'rcur.id IN' + str(search_currency_ids).replace('[', '(').replace(']', ')')

                is_same_currency = False
                if not other_currency_id or bulk.currency_id == other_currency_id:
                    is_same_currency = True

                if bulk.partner_id and bulk.partner_type == 'customer':
                    payment_type = 'receivable'
                elif bulk.partner_id and bulk.partner_type == 'supplier':
                    payment_type = 'payable'

                credentials = {
                    'partner_id': bulk.partner_id.id,
                    'company_id': self.env.user.company_id.id,
                    'reconciled': False,
                    'payment_type': payment_type,
                    'sql_currency_string': sql_currency_string,
                    'sql_journal_string': sql_journal_string,
                }
                query = """
                    SELECT
                        am.name AS move_name,
                        aml.id AS move_line_id,
                        aml.account_id AS account_id,
                        aml.date AS date_original,
                        aml.date_maturity AS date_due,
                        aml.currency_id AS currency_id,
                        CASE WHEN aml.credit > 0.0 THEN aml.credit
                           ELSE aml.debit
                        END AS amount_original,
                        aml.amount_residual AS amount_unreconciled,
                        CASE WHEN aml.credit > 0.0 THEN 'dr'
                           ELSE 'cr'
                        END AS line_type,
                        aml.amount_currency AS foregin_original,
                        aml.amount_residual_currency AS foreign_unreconciled,
                        am.id AS move_id
                        FROM account_move_line aml
                        LEFT JOIN account_move am ON (am.id = aml.move_id)
                        LEFT JOIN account_account acc ON (acc.id = aml.account_id)
                        LEFT JOIN account_account_type acct ON (acct.id = acc.user_type_id)
                        LEFT JOIN res_currency rcur ON rcur.id = aml.currency_id
                        LEFT JOIN account_journal ajor ON ajor.id = aml.journal_id
                        WHERE
                        aml.partner_id = {partner_id} AND aml.reconciled={reconciled} AND acct.type = '{payment_type}' AND {sql_currency_string} AND
                        {sql_journal_string} AND aml.company_id={company_id}
                        ORDER BY aml.create_date
                """.format(**credentials)
                self.env.cr.execute(query)
                account_move_lines = self.env.cr.fetchall()
                # remaining_amount = float_round(self.amount, currency_id.decimal_places)
                for line in account_move_lines:
                    foreign_original = 0.0
                    foreign_unreconciled = 0.0
                    if line[5] and other_currency_id and other_currency_id.id == line[5]:
                        foreign_original = float_round(abs(line[9]), other_currency_id.decimal_places)
                        foreign_unreconciled = float_round(abs(line[10]), other_currency_id.decimal_places)
                    elif not self.other_currency_id and line[5] and currency_id == line[5]:
                        foreign_original = float_round(abs(line[9]), currency_id.decimal_places)
                        foreign_unreconciled = float_round(abs(line[10]), currency_id.decimal_places)

                    amount_original = float_round(company_currency.compute(line[6] or 0.0, currency_id), currency_id.decimal_places)
                    amount_unreconciled = float_round(company_currency.compute(abs(line[7]), company_currency), currency_id.decimal_places)

                    line_currency_id = line[5] or company_currency.id
                    line_currency = ResCurrency.browse(line_currency_id)
                    invoice_rate = line_currency.with_context(date=line[3]).rate
                    invoice_direct_rate = line_currency.with_context(date=line[3]).direct_rate

                    invoice_ref = ''
                    if bulk.partner_type == 'supplier':
                        AccountInvoice = self.env['account.invoice']
                        invoice = AccountInvoice.search([('move_id', '=', line[11])])
                        invoice_ref = invoice.reference
                    rs = {
                        'name': line[0],
                        'type': line[8],
                        'move_line_id': line[1],
                        'reference': invoice_ref or '',
                        'account_id': line[2],
                        'date_original': line[3],
                        'date_due': line[4],
                        'amount_original': float_round(amount_original, currency_id.decimal_places),
                        'amount_unreconciled': float_round(amount_unreconciled, currency_id.decimal_places),
                        'currency_id': line_currency_id,
                        'company_currency_id': company_currency.id,
                        'foreign_amount': float_round(foreign_original, other_currency_id.decimal_places),
                        'foreign_unreconciled': float_round(foreign_unreconciled, other_currency_id.decimal_places),
                        'invoice_rate': invoice_rate,
                        'invoice_direct_rate': invoice_direct_rate,
                        'payment_rate': self.exchange_rate,
                        'payment_direct_rate': self.direct_exchange_rate,
                        'is_same_currency': is_same_currency,
                        'show_invoices': self.show_invoices,
                        'payment_id': bulk.id,
                        'diff_rate': (self.exchange_rate - invoice_rate),
                        'diff_direct_rate': (self.direct_exchange_rate - invoice_direct_rate),
                    }
                    self.env.cr.execute("""
                        INSERT INTO account_bulk_payment_line
                        (   name,
                            type,
                            move_line_id,
                            reference ,
                            account_id ,
                            amount_original ,
                            amount_unreconciled,
                            currency_id,
                            company_currency_id,
                            foreign_amount,
                            foreign_unreconciled,
                            invoice_rate,
                            invoice_direct_rate,
                            payment_rate,
                            payment_direct_rate,
                            is_same_currency,
                            show_invoices,
                            payment_id,
                            diff_rate,
                            diff_direct_rate)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (rs['name'], rs['type'], rs['move_line_id'], rs['reference'], rs['account_id'],
                          rs['amount_original'], rs['amount_unreconciled'], rs['currency_id'], rs['company_currency_id'],
                          rs['foreign_amount'], rs['foreign_unreconciled'], rs['invoice_rate'], rs['invoice_direct_rate'], rs['payment_rate'],
                          rs['payment_direct_rate'], rs['is_same_currency'], rs['show_invoices'], rs['payment_id'], rs['diff_rate'], rs['diff_direct_rate']))
            return True

    def create_exchange_rate_entry(self, currency, line, amount):
        if not self.company_id.currency_exchange_journal_id:
            raise UserError(_("You should configure the 'Exchange Rate Journal' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
        if not self.company_id.income_currency_exchange_account_id.id:
            raise UserError(_("You should configure the 'Gain Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
        if not self.company_id.expense_currency_exchange_account_id.id:
            raise UserError(_("You should configure the 'Loss Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))

        # The move date should be the maximum date between payment and invoice (in case
        # of payment in advance). However, we should make sure the move date is not
        # recorded after the end of year closing.
        # if move_date > rec.company_id.fiscalyear_lock_date:
        #     move_vals['date'] = move_date

        # diff_in_currency = line.currency_id.round(line.diff_direct_rate * line.amount_foregin)
        if amount < 0.0:
            if self.payment_type == 'inbound':
                vals = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': 0.0,
                    'credit': abs(amount),
                    'account_id': line.account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
                # line_to_reconcile = self.env['account.move.line'].create(vals)
                vals1 = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': abs(amount),
                    'credit': 0.0,
                    'account_id': self.company_id.currency_exchange_journal_id.default_debit_account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    # 'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
            elif self.payment_type == 'outbound':
                vals = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': abs(amount),
                    'credit': 0.0,
                    'account_id': line.account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
                # line_to_reconcile = self.env['account.move.line'].create(vals)
                vals1 = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': 0.0,
                    'credit': abs(amount),
                    'account_id': self.company_id.currency_exchange_journal_id.default_credit_account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    # 'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
        elif amount > 0.0:
            if self.payment_type == 'inbound':
                vals = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': abs(amount),
                    'credit': 0.0,
                    'account_id': line.account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
                # line_to_reconcile = self.env['account.move.line'].create(vals)
                vals1 = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': 0.0,
                    'credit': abs(amount),
                    'account_id': self.company_id.currency_exchange_journal_id.default_credit_account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    # 'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
            elif self.payment_type == 'outbound':
                vals = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': 0.0,
                    'credit': abs(amount),
                    'account_id': line.account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
                # line_to_reconcile = self.env['account.move.line'].create(vals)
                vals1 = {
                    'name': self.name,  # _('Currency exchange rate difference'), TODO: commented due to BASKIN-93
                    'debit': abs(amount),
                    'credit': 0.0,
                    'account_id': self.company_id.currency_exchange_journal_id.default_debit_account_id.id,
                    'currency_id': currency.id,
                    'partner_id': self.partner_id.id,
                    'analytic_account_id': self.account_analytic_id.id,
                    'payment_id': self.id,
                    # 'payment_move_line_id': line.move_line_id.id,
                    'company_id': self.company_id.id,
                    'amount_currency': 0.0,
                }
        move_vals = {
            'journal_id': self.company_id.currency_exchange_journal_id.id,
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id
        }
        move_vals['line_ids'] = [(0, 0, vals), (0, 0, vals1)]
        move = self.env['account.move'].create(move_vals)
        # move.post()
        return move

    def _get_liquidity_move_line_vals(self, amount):
        name = self.name
        if self.payment_type == 'transfer':
            name = _('Transfer to %s') % self.destination_journal_id.name
        vals = {
            'name': name,
            'account_id': self.payment_type in ('outbound', 'transfer') and self.journal_id.default_debit_account_id.id or self.journal_id.default_credit_account_id.id,
            'payment_id': self.id,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
            'payment_via': self.payment_via,
            'cheque_no': self.cheque_no,
        }
        if self.other_currency_id:
            vals['currency_id'] = self.other_currency_id != self.company_id.currency_id and self.other_currency_id.id or False

        # If the journal has a currency specified, the journal item need to be expressed in this currency
        if self.journal_id.currency_id and self.currency_id != self.journal_id.currency_id:
            amount = self.currency_id.with_context(date=self.payment_date).compute(amount, self.journal_id.currency_id)
            debit, credit, amount_currency, dummy = self.env['account.move.line'].with_context(date=self.payment_date).compute_amount_fields(amount, self.journal_id.currency_id, self.company_id.currency_id)
            vals.update({
                'amount_currency': amount_currency,
                'currency_id': self.journal_id.currency_id.id,
            })
        return vals

    def _get_shared_move_line_vals(self, debit, credit, amount_currency, move_id, invoice_id=False):
        result = super(AccountBulkPayment, self)._get_shared_move_line_vals(debit, credit, amount_currency, move_id, invoice_id)
        result['name'] = self.name
        result['cheque_no'] = self.cheque_no
        return result

    def _get_counterpart_move_line_vals(self, invoice=False):
        result = super(AccountBulkPayment, self)._get_counterpart_move_line_vals(invoice)
        result['name'] = self.name
        return result

    def _create_payment_entry(self, amount):
        """ Create a journal entry corresponding to a payment, if the payment references invoice(s) they are reconciled.
            Return the journal entry.
        """
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        invoice_currency = False
        if self.invoice_ids and all([x.currency_id == self.invoice_ids[0].currency_id for x in self.invoice_ids]):
            # if all the invoices selected share the same currency, record the paiement in that currency too
            invoice_currency = self.invoice_ids[0].currency_id

        if self.bulk_payment and self.show_invoices == 'foreign':
            bulk_payment_currency_rate = self.env.context.get('bulk_payment_currency_rate') or False
            debit, credit, amount_currency, currency_id = aml_obj.with_context(
                            date=self.payment_date, bulk_payment_currency=bulk_payment_currency_rate).compute_amount_fields(
                            amount, self.other_currency_id, self.company_id.currency_id, invoice_currency)
        else:
            debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(amount, self.currency_id, self.company_id.currency_id, invoice_currency)
        move = self.env['account.move'].create(self._get_move_vals())

        # Write line corresponding to invoice payment
        my_context = self.env.context.copy()
        payment_move_line_id = self.env.context.get('payment_move_line_id', False)
        my_context.update(account_analytic_id=self.account_analytic_id.id if self.account_analytic_id else False)
        counterpart_aml_dict = self.with_context(my_context)._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
        counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
        counterpart_aml_dict.update({'currency_id': currency_id, 'payment_via': self.payment_via, 'payment_move_line_id': payment_move_line_id})
        counterpart_aml = aml_obj.create(counterpart_aml_dict)

        # Reconcile with the invoices
        if self.payment_difference_handling == 'reconcile' and self.payment_difference:
            my_context = self.env.context.copy()
            my_context.update(account_analytic_id=self.account_analytic_id.id if self.account_analytic_id else False)
            writeoff_line = self.with_context(my_context)._get_shared_move_line_vals(0, 0, 0, move.id, False)
            debit_wo, credit_wo, amount_currency_wo, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(self.payment_difference, self.currency_id, self.company_id.currency_id, invoice_currency)
            writeoff_line['name'] = _('Counterpart')
            writeoff_line['account_id'] = self.writeoff_account_id.id
            writeoff_line['debit'] = debit_wo
            writeoff_line['credit'] = credit_wo
            writeoff_line['amount_currency'] = amount_currency_wo
            writeoff_line['currency_id'] = currency_id
            # Longdt: Add analytic account to writeoff_line
            writeoff_line['account_analytic_id'] = self.account_analytic_id and self.account_analytic_id.id or False
            writeoff_line = aml_obj.create(writeoff_line)
            if counterpart_aml['debit']:
                counterpart_aml['debit'] += credit_wo - debit_wo
            if counterpart_aml['credit']:
                counterpart_aml['credit'] += debit_wo - credit_wo
            counterpart_aml['amount_currency'] -= amount_currency_wo
        new_ctx = self.env.context.copy()
        new_ctx.update(account_analytic_id=self.account_analytic_id and self.account_analytic_id.id or False)
        if not self.env.context.get('from_baskin'):
            self.with_context(new_ctx).invoice_ids.register_payment(counterpart_aml)

        # Write counterpart lines
        if self.bulk_payment and self.show_invoices == 'foreign':
            if not self.other_currency_id != self.company_id.currency_id:
                amount_currency = 0
        else:
            if not self.currency_id != self.company_id.currency_id:
                amount_currency = 0
        my_context = self.env.context.copy()
        my_context.update(account_analytic_id=self.account_analytic_id.id if self.account_analytic_id else False)
        liquidity_aml_dict = self.with_context(my_context)._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
        liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
        aml_obj.create(liquidity_aml_dict)
        move.post()
        return move

    @api.multi
    def unreconcile_entry(self):
        msg = "Below Mentioned entries already matched with Bank Reconciliation statement, you cannot Unreconcile!. \n To Delete this entries, You have to make set to draft bank Reconciliation entry. %s"
        for rec in self:
            bank_statements = rec.move_line_ids.filtered(lambda r: r.bank_state == 'match')
            if bank_statements:
                bank_statement_names = [bank.move_id.name + ' - ' + bank.bank_statement_id.name for bank in bank_statements]
                raise ValidationError(_(msg % ('\n'.join(bank_statement_names))))

            for move in rec.move_line_ids.mapped('move_id'):
                move.line_ids.remove_move_reconcile()
                move.button_cancel()
                move.unlink()
            rec.write({'state': 'cancel'})
        return True

    @api.multi
    def refresh_entry(self):
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            line_dr_ids = []
            line_cr_ids = []

            account_move_lines = self.env['account.move.line']
            company_currency = self.env.user.company_id.currency_id
            currency_id = self.env.user.company_id.currency_id

            if rec.bulk_payment:
                search_currency_ids = []
                if rec.show_invoices == 'base':
                    search_currency_ids.append(False)
                    search_currency_ids.append(currency_id.id)
                else:
                    search_currency_ids.append(self.other_currency_id.id)

                is_same_currency = False
                if rec.currency_id == rec.other_currency_id:
                    is_same_currency = True

                if rec.partner_id and rec.partner_type == 'customer':
                    account_move_lines = AccountMoveLine.search([
                        ('partner_id', '=', self.partner_id.id),
                        ('reconciled', '=', False),
                        ('account_id.user_type_id.type', '=', 'receivable'),
                        ('currency_id', 'in', search_currency_ids),
                        ('journal_id.type', 'in', ('sale', 'purchase'))
                    ])
                elif rec.partner_id and rec.partner_type == 'supplier':
                    account_move_lines = AccountMoveLine.search([
                        ('partner_id', '=', self.partner_id.id),
                        ('reconciled', '=', False),
                        ('account_id.user_type_id.type', '=', 'payable'),
                        ('currency_id', 'in', search_currency_ids),
                    ])
                # remaining_amount = rec.amount
                for line in account_move_lines:
                    # foreign_original = 0.0
                    foreign_unreconciled = 0.0
                    if line.currency_id and rec.other_currency_id and rec.other_currency_id.id == line.currency_id.id:
                        # foreign_original = abs(line.amount_currency)
                        foreign_unreconciled = abs(line.amount_residual_currency)
                    elif not rec.other_currency_id and line.currency_id and currency_id == line.currency_id.id:
                        # foreign_original = abs(line.amount_currency)
                        foreign_unreconciled = abs(line.amount_residual_currency)

                    amount_original = company_currency.compute(line.credit or line.debit or 0.0, currency_id)
                    amount_unreconciled = company_currency.compute(abs(line.amount_residual), company_currency)

                    line_currency_id = line.currency_id and line.currency_id.id or company_currency and company_currency.id
                    invoice_rate = line.currency_id.with_context(date=line.date).rate
                    invoice_direct_rate = line.currency_id.with_context(date=line.date).direct_rate

                    invoice_ref = ''
                    if self.partner_type == 'supplier':
                        AccountInvoice = self.env['account.invoice']
                        invoice = AccountInvoice.search([('move_id', '=', line.move_id.id)])
                        invoice_ref = invoice.reference
                    rs = {
                        'name': line.move_id.name,
                        'type': line.credit and 'dr' or 'cr',
                        'move_line_id': line.id,
                        'reference': invoice_ref,
                        'account_id': line.account_id.id,
                        'date_original': line.date,
                        'date_due': line.date_maturity,
                        'amount_original': amount_original,
                        'amount_unreconciled': amount_unreconciled,
                        'currency_id': line_currency_id,
                        'company_currency_id': company_currency and company_currency.id,
                        # 'foreign_amount': foreign_original,
                        'foreign_unreconciled': foreign_unreconciled,
                        'invoice_rate': invoice_rate,
                        'invoice_direct_rate': invoice_direct_rate,
                        'payment_rate': self.exchange_rate,
                        'payment_direct_rate': self.direct_exchange_rate,
                        'is_same_currency': is_same_currency,
                        # 'amount': min(abs(remaining_amount), amount_unreconciled) or 0.0 if self.show_invoices == 'base' else 0.0,
                        'show_invoices': self.show_invoices,
                        # 'reconcile': False,
                        'diff_rate': (self.exchange_rate - invoice_rate),
                        'diff_direct_rate': (self.direct_exchange_rate - invoice_direct_rate),
                    }
                    if rec.payment_type == 'inbound':
                        credit_line = rec.line_cr_ids.filtered(lambda r: r.move_line_id.id == rs['move_line_id'])
                        if credit_line:
                            rs['amount'] = credit_line.amount
                            rs['amount_foregin'] = credit_line.amount_foregin
                            rs['reconcile'] = credit_line.reconcile
                    elif rec.payment_type == 'outbound':
                        debit_line = rec.line_dr_ids.filtered(lambda r: r.move_line_id.id == rs['move_line_id'])
                        if debit_line:
                            rs['amount'] = debit_line.amount
                            rs['amount_foregin'] = debit_line.amount_foregin
                            rs['reconcile'] = debit_line.reconcile

                    # amount = 0.0
                    # amount_foregin = 0.0
                    # if rec.show_invoices == 'foreign':
                    #     if rs['payment_direct_rate'] and rs['currency_id'] and rs['company_currency_id'] and rs['currency_id'] != rs['company_currency_id']:
                    #         amount_foregin = rs['foreign_unreconciled']
                    #         amount = rs['foreign_unreconciled'] * rs['payment_direct_rate']  # self.amount_unreconciled  # s
                    #         # self.amount = self.foreign_unreconciled / self.payment_direct_rate
                    #     elif rs['currency_id'] and rs['company_currency_id'] and rs['currency_id'] == rs['company_currency_id']:
                    #         amount_foregin = self.foreign_unreconciled
                    # else:
                    #     amount = rs['amount_unreconciled']

                    # rs['amount'] = amount
                    # rs['amount_foregin'] = amount_foregin
                    # if rs['amount_unreconciled'] == rs['amount'] and rs['show_invoices'] == 'base':
                    #     rs['reconcile'] = True

                    if rs['type'] == 'cr':
                        # if rec.payment_type == 'inbound':
                        #     rs.update({'reconcile': True})
                        line_cr_ids.append((0, 0, rs))
                    else:
                        # if rec.payment_type == 'outbound':
                        #     rs.update({'reconcile': True})
                        line_dr_ids.append((0, 0, rs))

            rec.line_cr_ids.unlink()
            rec.line_dr_ids.unlink()
            rec.with_context(from_refresh=True).write({'line_cr_ids': line_cr_ids, 'line_dr_ids': line_dr_ids})
        return True

    @api.multi
    def post_entry(self):
        for rec in self:
            self._check_before_validate()
            rec._check_paid_amount()
            if rec.payment_type == 'inbound' and rec.line_dr_ids or rec.payment_type == 'outbound' and rec.line_cr_ids:
                return {
                    'view_id': self.env.ref('baskin_bulk_payment.wizard_payment_remark_view').ids,
                    'view_type': 'form',
                    "view_mode": 'form',
                    'res_model': 'wizard.payment.remark',
                    'type': 'ir.actions.act_window',
                    'target': 'new'
                }
            else:
                rec.post()

    @api.multi
    def post(self):
        """ Create the journal items for the payment and update the payment's state to 'posted'.
            A journal entry is created containing an item in the source liquidity account (selected journal's default_debit or default_credit)
            and another in the destination reconciliable account (see _compute_destination_account_id).
            If invoice_ids is not empty, there will be one reconciliable move line per invoice to reconcile with.
            If the payment is a transfer, a second journal entry is created in the destination journal to receive money from the transfer account.
        """
        company_currency = self.env.user.company_id.currency_id
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only a draft payment can be posted. Trying to post a payment in state %s.") % rec.state)

            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            sequence_code = ''
            # Use the right sequence to set the name
            if rec.payment_type == 'transfer':
                sequence_code = 'account.payment.transfer'
            else:
                if rec.partner_type == 'customer':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.customer.invoice'
                        if rec.payment_via == 'bulk':
                            sequence_code = 'account.payment.bulk.customer.invoice'
                        elif rec.payment_via == 'deposit':
                            sequence = self.env['ir.sequence'].search([
                                ('code', 'in', ('customer.deposit.payment.gssb', 'customer.deposit.payment.mssb')),
                                ('company_id', '=', self.env.user.company_id.id)
                            ], limit=1)
                            sequence_code = sequence.code
                            # if self.env.user.company_id.name == 'Golden Scoop Sdn Bhd':
                            #     sequence_code = 'customer.deposit.payment.gssb'
                            # elif self.env.user.company_id.name == 'Mega Scoop Pte Ltd':
                            #     sequence_code = 'customer.deposit.payment.mssb'

                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.customer.refund'
                        if rec.payment_via == 'bulk':
                            sequence_code = 'account.payment.bulk.customer.refund'
                        elif rec.payment_via == 'deposit':
                            sequence = self.env['ir.sequence'].search([
                                ('code', 'in', ('vendor.deposit.payment.gssb', 'vendor.deposit.payment.mssb')),
                                ('company_id', '=', self.env.user.company_id.id)
                            ], limit=1)
                            sequence_code = sequence.code

                            # if self.env.user.company_id.name == 'Golden Scoop Sdn Bhd':
                            #     sequence_code = 'vendor.deposit.payment.gssb'
                            # elif self.env.user.company_id.name == 'Mega Scoop Pte Ltd':
                            #     sequence_code = 'vendor.deposit.payment.mssb'

                if rec.partner_type == 'supplier':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.supplier.refund'
                        if rec.payment_via == 'bulk':
                            sequence_code = 'account.payment.bulk.supplier.refund'
                        elif rec.payment_via == 'deposit':
                            sequence = self.env['ir.sequence'].search([
                                ('code', 'in', ('customer.deposit.payment.gssb', 'customer.deposit.payment.mssb')),
                                ('company_id', '=', self.env.user.company_id.id)
                            ], limit=1)
                            sequence_code = sequence.code
                            # if self.env.user.company_id.name == 'Golden Scoop Sdn Bhd':
                            #     sequence_code = 'customer.deposit.payment.gssb'
                            # elif self.env.user.company_id.name == 'Mega Scoop Pte Ltd':
                            #     sequence_code = 'customer.deposit.payment.mssb'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.supplier.invoice'
                        if rec.payment_via == 'bulk':
                            sequence_code = 'account.payment.bulk.supplier.invoice'
                        elif rec.payment_via == 'deposit':
                            sequence = self.env['ir.sequence'].search([
                                ('code', 'in', ('vendor.deposit.payment.gssb', 'vendor.deposit.payment.mssb')),
                                ('company_id', '=', self.env.user.company_id.id)
                            ], limit=1)
                            sequence_code = sequence.code
                            # if self.env.user.company_id.name == 'Golden Scoop Sdn Bhd':
                            #     sequence_code = 'vendor.deposit.payment.gssb'
                            # elif self.env.user.company_id.name == 'Mega Scoop Pte Ltd':
                            #     sequence_code = 'vendor.deposit.payment.mssb'

            rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)

            # Create the journal entry
            if rec.bulk_payment:
                ctx = self._context.copy()
                ctx['skip_full_reconcile_check'] = 'amount_residual_currency'
                sign = (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
                if rec.payment_type in ('inbound'):
                    for line in rec.line_cr_ids:
                        if self.show_invoices == 'foreign' and rec.other_currency_id and rec.currency_id != rec.other_currency_id:
                            amount = line.amount_foregin * sign
                        elif self.show_invoices == 'foreign' and rec.other_currency_id and rec.currency_id == rec.other_currency_id:
                            amount = line.amount_foregin * sign
                        else:
                            amount = line.amount * sign
                        move_line_ids = []
                        invoice_id = self.env['account.invoice'].search([('move_id', '=', line.move_line_id.move_id.id)])

                        if amount == 0.0:
                            continue
                        payment_move = rec.with_context(
                                bulk_payment_currency_rate=line.payment_direct_rate,
                                payment_move_line_id=line.move_line_id.id,
                                from_baskin=True)._create_payment_entry(amount)
                        payment_move.write({'ref': invoice_id.number})
                        # payment_move_line = self.env['account.move.line']
                        exchange_move = self.env['account.move']
                        if line.currency_id != company_currency and self.other_currency_id:
                            # currency_rate_difference = line.diff_direct_rate * line.amount_foregin
                            # if currency_rate_difference:
                            diff_in_currency = line.currency_id.round(line.diff_direct_rate * line.amount_foregin)
                            if diff_in_currency == 0.0 and line.amount_unreconciled != line.amount and line.reconcile:
                                diff_in_currency = abs(round(line.amount_unreconciled, 2) - round(line.amount, 2))
                            if diff_in_currency:
                                exchange_move = self.create_exchange_rate_entry(rec.other_currency_id, line, diff_in_currency)
                                exchange_move.write({'ref': invoice_id.number})
                                # payment_line = self.env['account.move.line']
                                for mvl in exchange_move.line_ids:
                                    if mvl.credit > 0.0 and diff_in_currency < 0.0:
                                        # payment_line |= mvl
                                        # invoice_id.with_context(ctx).register_payment(mvl)
                                        # move_line_ids.append(mvl.id)
                                        move_line_ids.insert(0, mvl.id)
                                    elif mvl.debit > 0.0 and diff_in_currency > 0.0:
                                        # payment_line |= mvl
                                        # invoice_id.with_context(ctx).register_payment(mvl)
                                        # move_line_ids.append(mvl.id)
                                        move_line_ids.insert(0, mvl.id)
                                    # if not payment_move_line.reconciled:
                                    #     (payment_move_line + payment_line).reconcile()
                                    # else:
                                    #     invoice_id.with_context(ctx).register_payment(mvl)
                        if line.move_line_id:
                            move_line_ids.append(line.move_line_id.id)

                        for mvl in payment_move.line_ids:
                            if mvl.credit > 0:
                                # invoice_id.with_context(ctx).register_payment(mvl)
                                # payment_move_line = mvl
                                move_line_ids.insert(-1, mvl.id)

                        # Customer Invoice
                        # Scenario 1: Total Debit > Total Credit, Difference is Positive
                        # 1a. Invoice Rate > Payment Rate, It is a loss.
                        # -- Exchange rate move, Debit: Gain & Loss Account, Credit: Receivable Account.
                        # -- In order to make total debit equals to total credit, has to ADD the absolute difference
                        # -- from both lines.
                        # 1b. Payment Rate > Invoice Rate, It is a gain.
                        # -- Exchange rate move, Debit: Receivable Account, Credit: Gain & Loss Account
                        # -- In order to make total debit equals to total credit, has to DEDUCT the absolute difference to
                        # -- both lines.

                        # Scenario 2: Total Credit > Total Debit, Difference is Negative
                        # 2a. Invoice Rate > Payment Rate, It is a loss.
                        # -- Exchange rate move, Debit: Gain & Loss Account, Credit: Receivable Account.
                        # -- In order to make total debit equals to total credit, has to DEDUCT the absolute difference to
                        # -- both lines.
                        # 2b. Payment Rate > Invoice Rate, It is a gain.
                        # -- Exchange rate move, Debit: Receivable Account, Credit: Gain & Loss Account
                        # -- In order to make total debit equals to total credit, has to ADD the absolute difference
                        # -- from both lines.

                        # Due to difference's sign,
                        # 1a. ADD POSITIVE = (+)
                        # 1b. DEDUCT POSITIVE = (-)
                        # 2a. DEDUCT NEGATIVE = (+)
                        # 2b. ADD NEGATIVE = (-)
                        # Hence, will combine 1a. and 2a. to one logic, 1b. and 2b. to one logic.

                        # If there is no exchange rate move in last payment, then will simply create a new move to do
                        # the adjustment.

                        # if the invoice line is fully reconciled
                        if line.reconcile:
                            # get the total debit, total credit, and difference (total debit - total credit) of the
                            # move lines (invoice move line and payment move lines)
                            diff = rec._get_debit_credit_rounding(line.move_line_id, move_line_ids)
                            # if there is a difference then need to do adjustment
                            if diff['diff']:
                                # if there is an exchange rate move in last payment then do adjustment in the exchange
                                # rate move line else create new entry to do adjustment
                                if exchange_move:
                                    for currency_diff_line in exchange_move.line_ids:
                                        # if the move line belongs to receivable account
                                        if currency_diff_line.account_id.id == line.account_id.id:
                                            # if the receivable move line in debit side (Payment Rate > Invoice Rate),
                                            # should minus the difference
                                            if currency_diff_line.debit:
                                                currency_diff_line.write({'debit': currency_diff_line.debit - diff['diff']})
                                            # if the receivable move line in credit side (Invoice Rate > Payment Rate),
                                            # should plus the difference
                                            elif currency_diff_line.credit:
                                                currency_diff_line.write({'credit': currency_diff_line.credit + diff['diff']})
                                        # if the move line belongs to gain & loss account
                                        else:
                                            # if the gain loss move line in debit side (Invoice Rate > Payment Rate),
                                            # should plus the difference
                                            if currency_diff_line.debit:
                                                currency_diff_line.write({'debit': currency_diff_line.debit + diff['diff']})
                                            # if the gain loss move line in credit side (Payment Rate > Invoice Rate),
                                            # should minus the difference
                                            elif currency_diff_line.credit:
                                                currency_diff_line.write({'credit': currency_diff_line.credit - diff['diff']})
                                # no exchange move
                                else:
                                    diff_move = self._create_line_diff(line, diff['diff'])
                                    if diff_move:
                                        diff_line = diff_move.line_ids.filtered(lambda r: r.account_id.reconcile)
                                        move_line_ids.insert(1, diff_line.id)
                        if exchange_move:
                            exchange_move.post()
                        sorted_move_line_ids = move_line_ids
                        sorted_move_lines = self.env['account.move.line'].browse(sorted_move_line_ids)
                        sorted_move_lines.with_context(from_bulk_payment=True).reconcile()
                        rec.write({'move_ids': [(4, payment_move.id)]})
                # if payment_type == outbound
                else:
                    for line in rec.line_dr_ids:
                        if self.show_invoices == 'foreign' and rec.other_currency_id and rec.currency_id != rec.other_currency_id:
                            amount = line.amount_foregin * sign
                        elif self.show_invoices == 'foreign' and rec.other_currency_id and rec.currency_id == rec.other_currency_id:
                            amount = line.amount_foregin * sign
                        else:
                            amount = line.amount * sign

                        move_line_ids = []
                        invoice_id = self.env['account.invoice'].search([('move_id', '=', line.move_line_id.move_id.id)])

                        if amount == 0.0:
                            continue
                        payment_move = rec.with_context(
                                            bulk_payment_currency_rate=line.payment_direct_rate,
                                            payment_move_line_id=line.move_line_id.id,
                                            from_baskin=True)._create_payment_entry(amount)
                        # payment_move.write({'ref': invoice_id.number})
                        # TODO: commented this code due to task BASKIN - 93
                        # payment_move_line = self.env['account.move.line']
                        for mvl in payment_move.line_ids:
                            if mvl.debit > 0:
                                # invoice_id.with_context(ctx).register_payment(mvl)
                                # payment_move_line = mvl
                                move_line_ids.append(mvl.id)
                        exchange_move = self.env['account.move']
                        if line.currency_id != company_currency and self.other_currency_id:
                            # currency_rate_difference = line.diff_direct_rate * line.amount_foregin
                            # if currency_rate_difference:
                            diff_in_currency = line.currency_id.round(line.diff_direct_rate * line.amount_foregin)
                            if diff_in_currency == 0.0 and line.amount_unreconciled != line.amount and line.reconcile:
                                if round(line.amount_unreconciled, 2) - round(line.amount, 2) > 0:
                                    diff_in_currency = round(line.amount, 2) - round(line.amount_unreconciled, 2)
                                elif round(line.amount_unreconciled, 2) - round(line.amount, 2) < 0:
                                    diff_in_currency = round(line.amount, 2) - round(line.amount_unreconciled, 2)

                            if diff_in_currency:
                                exchange_move = self.create_exchange_rate_entry(rec.other_currency_id, line, diff_in_currency)
                                exchange_move.write({'ref': invoice_id.number})
                                # payment_line = self.env['account.move.line']
                                for mvl in exchange_move.line_ids:
                                    if mvl.credit > 0.0 and diff_in_currency > 0.0:
                                        # move_line_ids.append(mvl.id)
                                        move_line_ids.insert(0, mvl.id)

                                        # payment_line |= mvl
                                        # invoice_id.with_context(ctx).register_payment(mvl)
                                    elif mvl.debit > 0.0 and diff_in_currency < 0.0:
                                        # move_line_ids.append(mvl.id)
                                        move_line_ids.insert(0, mvl.id)
                                        # payment_line |= mvl
                                        # invoice_id.with_context(ctx).register_payment(mvl)
                                # if not payment_move_line.reconciled:
                                #     (payment_move_line + payment_line).reconcile()
                                # else:
                                #     invoice_id.with_context(ctx).register_payment(mvl)
                        if line.move_line_id:
                            move_line_ids.append(line.move_line_id.id)

                        # Supplier Invoice
                        # Scenario 1: Total Debit > Total Credit, Difference is Positive
                        # 1a. Invoice Rate > Payment Rate, It is a gain.
                        # -- Exchange rate move, Debit: Payable Account, Credit: Gain & Loss Account.
                        # -- In order to make total debit equals to total credit, has to DEDUCT the absolute difference
                        # -- from both lines.
                        # 1b. Payment Rate > Invoice Rate, It is a loss.
                        # -- Exchange rate move, Debit: Gain & Loss Account, Credit: Payable Account
                        # -- In order to make total debit equals to total credit, has to ADD the absolute difference to
                        # -- both lines.

                        # Scenario 2: Total Credit > Total Debit, Difference is Negative
                        # 2a. Invoice Rate > Payment Rate, It is a gain.
                        # -- Exchange rate move, Debit: Payable Account, Credit: Gain & Loss Account.
                        # -- In order to make total debit equals to total credit, has to ADD the absolute difference to
                        # -- both lines.
                        # 2b. Payment Rate > Invoice Rate, It is a loss.
                        # -- Exchange rate move, Debit: Gain & Loss Account, Credit: Payable Account
                        # -- In order to make total debit equals to total credit, has to DEDUCT the absolute difference
                        # -- from both lines.

                        # Due to difference's sign,
                        # 1a. DEDUCT POSITIVE = (-)
                        # 1b. ADD POSITIVE = (+)
                        # 2a. ADD NEGATIVE = (-)
                        # 2b. DEDUCT NEGATIVE = (+)
                        # Hence, will combine 1a. and 2a. to one logic, 1b. and 2b. to one logic.

                        # If there is no exchange rate move in last payment, then will simply create a new move to do
                        # the adjustment.

                        # if the invoice line is fully reconciled
                        if line.reconcile:
                            # get the total debit, total credit, and difference (total debit - total credit) of the
                            # move lines (invoice move line and payment move lines)
                            diff = rec._get_debit_credit_rounding(line.move_line_id, move_line_ids)
                            # if there is a difference then need to do adjustment
                            if diff['diff']:
                                # if there is an exchange rate move in last payment then do adjustment in the exchange
                                # rate move line else create new entry to do adjustment
                                if exchange_move:
                                    for currency_diff_line in exchange_move.line_ids:
                                        # if the move line belongs to payable account
                                        if currency_diff_line.account_id.id == line.account_id.id:
                                            # if the payable move line in debit side (Invoice Rate > Payment Rate),
                                            # should minus the difference
                                            if currency_diff_line.debit:
                                                currency_diff_line.write({'debit': currency_diff_line.debit - diff['diff']})
                                            # if the payable move line in credit side (Payment Rate > Invoice Rate),
                                            # should plus the difference
                                            elif currency_diff_line.credit:
                                                currency_diff_line.write({'credit': currency_diff_line.credit + diff['diff']})
                                        # if the move line belongs to gain & loss account
                                        else:
                                            # if the gain loss move line in debit side (Payment Rate > Invoice Rate),
                                            # should plus the difference
                                            if currency_diff_line.debit:
                                                currency_diff_line.write({'debit': currency_diff_line.debit + diff['diff']})
                                            # if the gain loss move line in credit side (Invoice Rate > Payment Rate),
                                            # should minus the difference
                                            elif currency_diff_line.credit:
                                                currency_diff_line.write({'credit': currency_diff_line.credit - diff['diff']})
                                # no exchange move
                                else:
                                    diff_move = self._create_line_diff(line, diff['diff'])
                                    if diff_move:
                                        diff_line = diff_move.line_ids.filtered(lambda r: r.account_id.reconcile)
                                        move_line_ids.insert(1, diff_line.id)
                        if exchange_move:
                            exchange_move.post()
                        sorted_move_lines = self.env['account.move.line'].browse(move_line_ids)
                        sorted_move_lines.with_context(from_bulk_payment=True).reconcile()
                        rec.write({'move_ids': [(4, payment_move.id)]})
            else:
                # Create the journal entry
                amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
                move = rec._create_payment_entry(amount)
                self.write({'move_id': move.id})
                # In case of a transfer, the first journal entry created debited the source liquidity account and credited
                # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
                if rec.payment_type == 'transfer':
                    transfer_credit_aml = move.line_ids.filtered(lambda r: r.account_id == rec.company_id.transfer_account_id)
                    transfer_debit_aml = rec._create_transfer_entry(amount)
                    (transfer_credit_aml + transfer_debit_aml).reconcile()
            rec.state = 'posted'

    def _get_debit_credit_rounding(self, line, lines_ids):
        company_currency = self.company_id.currency_id
        diff = 0.0
        credit_total = 0.0
        debit_total = 0.0
        MoveLine = self.env['account.move.line']
        move_lines = self.env['account.move.line'].browse(lines_ids)
        domain = []
        if line:
            domain.append(('payment_move_line_id', '=', line.id))
        if move_lines:
            domain.append(('id', 'not in', move_lines.ids))

        line_ids = []
        if domain:
            al_move_lines = MoveLine.search(domain)
            al_move_lines |= move_lines
            credit_total = company_currency.round(sum([p.credit for p in al_move_lines if p.credit > 0.0 and p.account_id.reconcile]))
            debit_total = company_currency.round(sum([p.debit for p in al_move_lines if p.debit > 0.0 and p.account_id.reconcile]))
            line_ids = al_move_lines.ids

        if line.matched_credit_ids:
            for l in line.matched_credit_ids:
                credit_total += company_currency.round(
                    l.credit_move_id.matched_debit_ids.filtered(lambda l: l.debit_move_id == line and l.credit_move_id.id not in line_ids).amount)
            # credit_total += company_currency.round(sum([p.credit_move_id.credit for p in line.matched_credit_ids if p.credit_move_id.credit > 0.0 and p.credit_move_id.account_id.reconcile and p.credit_move_id.id not in line_ids]))

        if line.matched_debit_ids:
            for l in line.matched_debit_ids:
                debit_total += company_currency.round(
                    l.debit_move_id.matched_credit_ids.filtered(lambda l: l.credit_move_id == line and l.debit_move_id.id not in line_ids).amount)
            # debit_total += company_currency.round(sum([p.debit_move_id.debit for p in line.matched_debit_ids if p.debit_move_id.debit > 0.0 and p.debit_move_id.account_id.reconcile and p.debit_move_id.id not in line_ids]))
        diff = company_currency.round((debit_total - credit_total))
        return {'diff': diff, 'credit_total': credit_total, 'debit_total': debit_total}

    def _create_line_diff(self, line, amount):
        vals = vals1 = {}
        if amount < 0.0:
            vals = {
                'name': self.name,
                'debit': abs(amount),
                'credit': 0,
                'account_id': line.account_id.id,
                'journal_id': self.journal_id.id,
                # 'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
                'payment_via': self.payment_via,
                'partner_id': self.partner_id.id,
                'analytic_account_id': self.account_analytic_id.id,
                'payment_id': self.id,
                'payment_move_line_id': line.move_line_id.id,
            }
            vals1 = {
                'name': self.name,
                'debit': 0,
                'credit': abs(amount),
                'account_id': self.company_id.currency_exchange_journal_id.default_debit_account_id.id,
                'journal_id': self.journal_id.id,
                # 'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
                'payment_via': self.payment_via,
                'partner_id': self.partner_id.id,
                'analytic_account_id': self.account_analytic_id.id,
                'payment_id': self.id,
                # 'payment_move_line_id': line.move_line_id.id,
            }
        elif amount > 0.0:
            vals = {
                'name': self.name,
                'debit': 0,
                'credit': amount,
                'account_id': line.account_id.id,
                'journal_id': self.journal_id.id,
                # 'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
                'payment_via': self.payment_via,
                'partner_id': self.partner_id.id,
                'analytic_account_id': self.account_analytic_id.id,
                'payment_id': self.id,
                'payment_move_line_id': line.move_line_id.id,
            }
            vals1 = {
                'name': self.name,
                'debit': amount,
                'credit': 0,
                'account_id': self.company_id.currency_exchange_journal_id.default_debit_account_id.id,
                'journal_id': self.journal_id.id,
                # 'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
                'payment_via': self.payment_via,
                'partner_id': self.partner_id.id,
                'analytic_account_id': self.account_analytic_id.id,
                'payment_id': self.id,
                # 'payment_move_line_id': line.move_line_id.id,
            }
        move_vals = {
            'journal_id': self.company_id.currency_exchange_journal_id.id,
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
        }
        move_vals['line_ids'] = [(0, 0, vals), (0, 0, vals1)]
        move = self.env['account.move'].create(move_vals)
        move.post()
        return move


class AccountBulkPaymentLine(models.Model):
    _name = 'account.bulk.payment.line'

    def _get_currency(self):
        return self.env.user.company_id.currency_id.id

    @api.depends('payment_rate', 'invoice_rate', 'payment_direct_rate', 'invoice_direct_rate')
    def _compute_rate(self):
        for line in self:
            line.diff_rate = line.payment_rate - line.invoice_rate
            line.diff_direct_rate = line.payment_direct_rate - line.invoice_direct_rate

    payment_id = fields.Many2one('account.payment', 'Payment', required=1, ondelete='cascade')
    name = fields.Char('Description', default='/')
    account_id = fields.Many2one('account.account', 'Account', required=True)
    partner_id = fields.Many2one(related='payment_id.partner_id', string='Partner')
    untax_amount = fields.Float('Untax Amount')
    reconcile = fields.Boolean('Full Reconcile')
    type = fields.Selection([('dr', 'Debit'), ('cr', 'Credit')], 'Dr/Cr')
    move_line_id = fields.Many2one('account.move.line', 'Journal Item', copy=False)
    date_original = fields.Date(related='move_line_id.date', string='Date', readonly=1)
    date_due = fields.Date(related='move_line_id.date_maturity', string='Due Date', readonly=1)
    amount_original = fields.Float('Original Amount', digits=0)
    amount_unreconciled = fields.Float('Base Currency Outstanding Amount', digits=0)

    amount = fields.Float('Payment Amount (Base)', digits=0)
    amount_foregin = fields.Float('Payment Amount (Foreign)', digits=0)
    backend_amount_foregin = fields.Float('Backend Payment Amount (Foreign)', digits=0)

    foreign_amount = fields.Float('Foreign Currency Amount', digits=0)
    foreign_unreconciled = fields.Float('Foreign Currency Outstanding Amount', digits=0)
    company_id = fields.Many2one('res.company', related='payment_id.company_id', string='Company', store=True, readonly=True)
    company_currency_id = fields.Many2one('res.currency', related='payment_id.currency_id', string='Currency', readonly=True, store=True)

    payment_rate = fields.Float('Payment Rate', digits=dp.get_precision('Currency Rate'))
    invoice_rate = fields.Float('Invoice Rate', digits=dp.get_precision('Currency Rate'))

    payment_direct_rate = fields.Float('Payment Rate (Direct)', digits=dp.get_precision('Currency Rate'))
    invoice_direct_rate = fields.Float('Invoice Rate (Direct)', digits=dp.get_precision('Currency Rate'))

    # diff_rate = fields.Float(compute='_compute_rate', string='Diff Rate', store=True, digits=dp.get_precision('Currency Rate'))
    # diff_direct_rate = fields.Float(compute='_compute_rate', string='Diff Rate (Direct)', store=True, digits=dp.get_precision('Currency Rate'))

    diff_rate = fields.Float('Diff Rate', digits=dp.get_precision('Currency Rate'))
    diff_direct_rate = fields.Float('Diff Rate (Direct)', digits=dp.get_precision('Currency Rate'))
    currency_id = fields.Many2one('res.currency', string='Currency')
    is_same_currency = fields.Boolean(string='Is Curreny Same?')
    # account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    show_invoices = fields.Selection([
                        ('base', 'Base Currency'),
                        ('foreign', 'Foreign Currency')],
                        string='Invoices Types')
    reference = fields.Char('Inv No/Ref')

    @api.constrains('amount_foregin', 'foreign_unreconciled')
    def _check_foregin_amount(self):
        for rec in self:
            if rec.amount_foregin > rec.foreign_unreconciled:
                raise ValidationError(_('Foregin Payment not more than Foreign Outstanding Payment!'))

    @api.onchange('reconcile')
    def onchange_reconcile(self):
        if not self.env.context.get('from_amount'):
            self.amount = 0.0
            self.amount_foregin = 0.0
        if self.payment_id.show_invoices == 'foreign':
            if self.reconcile and self.payment_direct_rate and self.currency_id and self.currency_id != self.company_currency_id:
                self.amount_foregin = float_round(self.foreign_unreconciled, self.currency_id.decimal_places)
                self.backend_amount_foregin = float_round(self.foreign_unreconciled, self.currency_id.decimal_places)
                self.amount = float_round(self.foreign_unreconciled, self.currency_id.decimal_places) * self.payment_direct_rate  # self.amount_unreconciled  # s
                # self.amount = self.foreign_unreconciled / self.payment_direct_rate
            elif self.reconcile and self.currency_id and self.currency_id == self.company_currency_id:
                self.amount_foregin = float_round(self.foreign_unreconciled, self.currency_id.decimal_places)
                self.backend_amount_foregin = float_round(self.foreign_unreconciled, self.currency_id.decimal_places)
        else:
            if self.reconcile:
                self.amount = float_round(self.amount_unreconciled, self.currency_id.decimal_places)

    @api.multi
    def onchange_amount(self, show_invoices, currency_id, foregin_currency_id, amount, amount_unreconciled, foregin_amount, foreign_unreconciled, payment_direct_rate):
        if self.env.context.get('from_amount'):
            reconcile = False
            if show_invoices == 'foreign' and currency_id and currency_id != foregin_currency_id:
                amount = float_round(foregin_amount * payment_direct_rate, self.currency_id.decimal_places)
                if float_round(foregin_amount, self.currency_id.decimal_places) == float_round(foreign_unreconciled, self.currency_id.decimal_places):
                    reconcile = True
            else:
                amount = float_round(amount, self.currency_id.decimal_places)
                amount_unreconciled = float_round(amount_unreconciled, self.currency_id.decimal_places)
                if amount == amount_unreconciled:
                    reconcile = True
            return {'value': {'reconcile': reconcile, 'amount': amount, 'amount_foregin': foregin_amount}}

    @api.model
    def create(self, vals):
        if vals.get('backend_amount_foregin'):
            vals['amount_foregin'] = vals['backend_amount_foregin']
        return super(AccountBulkPaymentLine, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('backend_amount_foregin'):
            vals['amount_foregin'] = vals['backend_amount_foregin']
        return super(AccountBulkPaymentLine, self).write(vals)
