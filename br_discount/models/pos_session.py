from openerp import models, api, fields, _
from openerp import tools
from datetime import datetime
from collections import OrderedDict
from openerp.addons.connector.queue.job import (
    job
)

from openerp.addons.connector.session import (
    ConnectorSession
)


@job
def _post_sale_voucher(session, model_name, pos_session_id):
    pos_session = session.env[model_name].browse(pos_session_id)
    if pos_session:
        pos_session.post_sale_voucher()

class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.multi
    def wkf_action_close(self):
        res = super(PosSession, self).wkf_action_close()
        session = ConnectorSession(self.env.cr, self.env.user.id, context=self.env.context)
        _post_sale_voucher.delay(session, 'pos.session', self.id)
        return res

    def create_picking(self):
        """
        Create picking immediately for each pos_order if it is:
        - a non-sales transaction
        - a transaction using redeem voucher
        - a transaction created to cancel another order from previous session (means we wont do this if user cancel transaction within that session)
        """
        for session in self:
            for order in session.order_ids:
                if order.lines and order.lines[0].non_sale or len(order.sale_voucher_ids) != 0:
                    order.create_picking()
        return super(PosSession, self).create_picking()

    def _create_sale_voucher_account_move(self, move_name, journal_id):
        start_at_datetime = datetime.strptime(self.start_at, tools.DEFAULT_SERVER_DATETIME_FORMAT)
        date_tz_user = fields.Datetime.context_timestamp(self, start_at_datetime)
        date_tz_user = date_tz_user.strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
        return self.env['account.move'].create({'ref': move_name + ' ' + 'Voucher', 'journal_id': journal_id, 'date': date_tz_user})

    def post_sale_voucher(self):
        """
        Redeemed Voucher sales don't belongs to outlet's sale,
        because of that need to create new journal entries to redirect sales amount to sale department
        :return:
        """
        account_move_lines = OrderedDict()
        # current_assets_account = self.env.ref('account.data_account_type_current_assets').id
        expenses_account_id = self.env.ref('account.data_account_type_expenses').id
        cost_revenue_id = self.env.ref('account.data_account_type_direct_costs').id
        def prepare_move_line(type, line_type, key, values):
            """ Group all account move lines with same key"""
            account_move_lines.setdefault(type, {})
            account_move_lines[type].setdefault(line_type, {})
            if key not in account_move_lines[type][line_type]:
                account_move_lines[type][line_type][key] = values
            else:
                account_move_lines[type][line_type][key]['credit'] += values['credit']
                account_move_lines[type][line_type][key]['debit'] += values['debit']

        for session in self:
            for order in session.order_ids:
                total_payment = sum([stm.amount for stm in order.statement_ids])
                for detail in order.sale_voucher_ids:
                    promotion = detail.voucher_id.promotion_id
                    outlet_analytic_account_id = detail.outlet_analytic_account_id.id
                    voucher_analytic_account_id = detail.analytic_account_id.id
                    voucher_type = detail.voucher_type
                    journal_account_id = detail.journal_id.default_debit_account_id.id

                    total_amount = detail.value + detail.unredeem_value
                    tax = detail.tax_ids[0] if detail.tax_ids else False
                    tax_id = tax.id if tax else False
                    tax_amount = float(tax.amount) / 100 if tax else 0
                    total_tax = round(total_amount * tax_amount / (1 + tax_amount), 2)
                    unredeem_sales = round(detail.unredeem_value / (1 + tax_amount), 2)

                    total_sales = total_amount - total_tax - unredeem_sales
                    # Payment
                    payment_debit_key = (journal_account_id, voucher_analytic_account_id, tax_id, voucher_type, detail.journal_id.id)
                    payment_credit_key = (journal_account_id, outlet_analytic_account_id, tax_id, voucher_type, detail.journal_id.id)

                    prepare_move_line('Payment_%s' % detail.journal_id.id, 'payment_debit', payment_debit_key, {
                        'name': detail.journal_id.name,
                        'account_id': journal_account_id,
                        'credit': 0,
                        'debit': total_amount,
                        'tax_line_id': False,
                        'analytic_account_id': voucher_analytic_account_id
                    })

                    prepare_move_line('Payment_%s' % detail.journal_id.id, 'payment_credit', payment_credit_key, {
                        'name': detail.journal_id.name,
                        'account_id': journal_account_id,
                        'credit': total_amount,
                        'debit': 0,
                        'tax_line_id': False,
                        'analytic_account_id': outlet_analytic_account_id
                    })
                    # Taxes on payment
                    if total_tax:
                        tax_payment_debit_key = (tax.account_id.id, outlet_analytic_account_id, tax_id, voucher_type, detail.journal_id.id)
                        tax_payment_credit_key = (tax.account_id.id if voucher_type == 'cash' else journal_account_id, voucher_analytic_account_id, tax_id, voucher_type, detail.journal_id.id)

                        prepare_move_line('Payment_%s' % detail.journal_id.id, 'tax_payment_debit', tax_payment_debit_key, {
                            'name': detail.journal_id.name + ' ' + _('Tax') + ' ' + tax.name,
                            'account_id': tax.account_id.id,
                            'credit': 0,
                            'debit': total_tax,
                            'tax_line_id': tax_id,
                            'analytic_account_id': outlet_analytic_account_id
                        })

                        prepare_move_line('Payment_%s' % detail.journal_id.id, 'tax_payment_credit', tax_payment_credit_key, {
                            'name': detail.journal_id.name + ' ' + _('Tax') + ' ' + tax.name,
                            'account_id': tax.account_id.id if voucher_type == 'cash' else journal_account_id,
                            'credit': total_tax,
                            'debit': 0,
                            'tax_line_id': tax_id,
                            'analytic_account_id': voucher_analytic_account_id
                        })

                    # Sales
                    if detail.unredeem_value:
                        unredeem_sales_debit_key = (detail.unredeem_income_account_id.id, outlet_analytic_account_id, tax_id, voucher_type)
                        unredeem_sales_credit_key = (detail.unredeem_income_account_id.id, voucher_analytic_account_id, tax_id, voucher_type)

                        prepare_move_line('Sales', 'unredeem_sales_debit', unredeem_sales_debit_key, {
                            'name': promotion.name,
                            'account_id': detail.unredeem_income_account_id.id,
                            'credit': 0,
                            'debit': unredeem_sales,
                            'tax_line_id': tax_id,
                            'analytic_account_id': outlet_analytic_account_id,
                        })

                        prepare_move_line('Sales', 'unredeem_sales_credit', unredeem_sales_credit_key, {
                            'name': promotion.name,
                            'account_id': detail.unredeem_income_account_id.id,
                            'credit': unredeem_sales,
                            'debit': 0,
                            'tax_line_id': tax_id,
                            'analytic_account_id': voucher_analytic_account_id,
                        })

                    sale_debit_key = (promotion.debit_account_id.id, outlet_analytic_account_id, tax_id, voucher_type)
                    sale_credit_key = (promotion.credit_account_id.id, voucher_analytic_account_id, tax_id, voucher_type)

                    prepare_move_line('Sales', 'sale_debit', sale_debit_key, {
                        'name': promotion.name,
                        'account_id': promotion.debit_account_id.id,
                        'credit': 0,
                        'debit': total_sales,
                        'tax_line_id': tax_id,
                        'analytic_account_id': outlet_analytic_account_id
                    })

                    prepare_move_line('Sales', 'sale_credit', sale_credit_key, {
                        'name': promotion.name,
                        'account_id': promotion.credit_account_id.id,
                        'credit': total_sales,
                        'debit': 0,
                        'tax_line_id': tax_id,
                        'analytic_account_id': voucher_analytic_account_id
                    })
                    voucher_rate = float(total_amount) / total_payment if total_payment else 0
                    if order.picking_id and not order.is_service_order:
                        stock_journals = self.env['account.move'].search([('ref', '=', order.picking_id.name)])
                        for stock_journal in stock_journals:
                            lines = stock_journal.line_ids.filtered(lambda x: x.account_id.user_type_id.id in (expenses_account_id, cost_revenue_id))
                            for sjl in lines:
                                if sjl.credit:
                                    prepare_move_line('Stock_%s' % stock_journal.journal_id.id, 'stock_journal_debit', (sjl.account_id.id, outlet_analytic_account_id, stock_journal.journal_id.id), {
                                        'name': "Stock Voucher",
                                        'account_id': sjl.account_id.id,
                                        'credit': 0,
                                        'debit': sjl.credit * voucher_rate,
                                        'tax_line_id': False,
                                        'analytic_account_id': outlet_analytic_account_id
                                    })
                                    prepare_move_line('Stock_%s' % stock_journal.journal_id.id, 'stock_journal_credit', (sjl.account_id.id, voucher_analytic_account_id, stock_journal.journal_id.id), {
                                        'name': "Stock Voucher",
                                        'account_id': sjl.account_id.id,
                                        'credit': sjl.credit * voucher_rate,
                                        'debit': 0,
                                        'tax_line_id': False,
                                        'analytic_account_id': voucher_analytic_account_id
                                    })
                                elif sjl.debit:
                                    prepare_move_line('Stock_%s' % stock_journal.journal_id.id, 'stock_journal_debit', (sjl.account_id.id, outlet_analytic_account_id, stock_journal.journal_id.id), {
                                        'name': "Stock Voucher",
                                        'account_id': sjl.account_id.id,
                                        'credit': 0,
                                        'debit': sjl.debit * voucher_rate,
                                        'tax_line_id': False,
                                        'analytic_account_id': voucher_analytic_account_id
                                    })
                                    prepare_move_line('Stock_%s' % stock_journal.journal_id.id, 'stock_journal_credit', (sjl.account_id.id, voucher_analytic_account_id, stock_journal.journal_id.id), {
                                        'name': "Stock Voucher",
                                        'account_id': sjl.account_id.id,
                                        'credit': sjl.debit * voucher_rate,
                                        'debit': 0,
                                        'tax_line_id': False,
                                        'analytic_account_id': outlet_analytic_account_id
                                    })

        # Create account move
        moves = self.env['account.move']
        for t in account_move_lines:
            vals = []
            for l_t in account_move_lines[t]:
                for k, v in account_move_lines[t][l_t].items():
                    vals.append((0, 0, v))
            if vals:
                if 'Payment' in t or 'Stock' in t:
                    journal_id = int(t.split('_')[-1])
                    je_name = self.name + ' ' + ('Payment' if 'Payment' in t else 'Stock')
                elif t == 'Sales' and vals:
                    journal_id = self.config_id.journal_id.id
                    je_name = self.name + ' ' + 'Sales'
                if journal_id and je_name:
                    move = self.with_context({})._create_sale_voucher_account_move(je_name, journal_id)
                    move.write({'line_ids': vals})
                    moves |= move
        if moves:
            moves.post()
