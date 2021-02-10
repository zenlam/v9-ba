from openerp.osv import osv, fields
from openerp import SUPERUSER_ID
from openerp.exceptions import UserError
from openerp.tools.translate import _


class PosOrder(osv.osv):
    _inherit = 'pos.order'

    # Add Analytic Account for all line http://phabricator.hanelsoft.vn:8080/T4388
    def _create_account_move_line(self, cr, uid, ids, session=None, move_id=None, context=None):
        # Tricky, via the workflow, we only have one id in the ids variable
        """Create a account move line of order grouped by products or not."""
        account_move_obj = self.pool.get('account.move')
        account_tax_obj = self.pool.get('account.tax')
        property_obj = self.pool.get('ir.property')
        cur_obj = self.pool.get('res.currency')

        # session_ids = set(order.session_id for order in self.browse(cr, uid, ids, context=context))

        if session and not all(session.id == order.session_id.id for order in self.browse(cr, uid, ids, context=context)):
            raise UserError(_('Selected orders do not have the same session!'))

        grouped_data = {}
        have_to_group_by = session and session.config_id.group_by or False

        for order in self.browse(cr, uid, ids, context=context):
            if order.account_move:
                continue
            if order.state != 'paid':
                continue

            current_company = order.sale_journal.company_id

            group_tax = {}
            account_def = property_obj.get(cr, uid, 'property_account_receivable_id', 'res.partner', context=context)

            order_account = order.partner_id and \
                            order.partner_id.property_account_receivable_id and \
                            order.partner_id.property_account_receivable_id.id or \
                            account_def and account_def.id

            if move_id is None:
                # Create an entry for the sale
                move_id = self._create_account_move(cr, uid, order.session_id.start_at, order.name, order.sale_journal.id, order.company_id.id, context=context)

            move = account_move_obj.browse(cr, SUPERUSER_ID, move_id, context=context)

            def insert_data(data_type, values):
                # if have_to_group_by:

                # 'quantity': line.qty,
                # 'product_id': line.product_id.id,
                values.update({
                    'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(order.partner_id).id or False,
                    'move_id': move_id,
                })

                if data_type == 'product':
                    key = ('product', values['partner_id'], (values['product_id'], values['name']), values['analytic_account_id'], values['debit'] > 0, values['account_id'])
                elif data_type == 'tax':
                    key = ('tax', values['partner_id'], values['tax_line_id'], values['debit'] > 0, values['account_id'], values['analytic_account_id'])
                elif data_type == 'counter_part':
                    key = ('counter_part', values['partner_id'], values['account_id'], values['debit'] > 0, values['analytic_account_id'])
                else:
                    return

                grouped_data.setdefault(key, [])

                # if not have_to_group_by or (not grouped_data[key]):
                #     grouped_data[key].append(values)
                # else:
                #     pass

                if have_to_group_by:
                    if not grouped_data[key]:
                        grouped_data[key].append(values)
                    else:
                        for line in grouped_data[key]:
                            if line.get('tax_code_id') == values.get('tax_code_id'):
                                current_value = line
                                self.set_grouped_line(current_value, values)
                                break
                        else:
                            grouped_data[key].append(values)
                else:
                    grouped_data[key].append(values)

            # because of the weird way the pos order is written, we need to make sure there is at least one line,
            # because just after the 'for' loop there are references to 'line' and 'income_account' variables (that
            # are set inside the for loop)
            # TOFIX: a deep refactoring of this method (and class!) is needed in order to get rid of this stupid hack
            assert order.lines, _('The POS order must have lines when calling this method')
            # Create an move for each order line

            cur = order.pricelist_id.currency_id
            iindex = 0
            order_fiscal = {}
            if order.fiscal_position_id:
                order_fiscal = order.fiscal_position_id

            for line in order.lines:
                amount = line.price_subtotal

                # Search for the income account
                if line.product_id.property_account_income_id.id:
                    income_account = line.product_id.property_account_income_id.id
                elif line.product_id.categ_id.property_account_income_categ_id.id:
                    income_account = line.product_id.categ_id.property_account_income_categ_id.id
                else:
                    raise UserError(_('Please define income ' \
                                      'account for this product: "%s" (id:%d).') \
                                    % (line.product_id.name, line.product_id.id))
                fiscal_position = {}
                if line.promotion_ids:
                    for promotion in line.promotion_ids:
                        for fiscal in promotion.fiscal_position_ids:
                            order_fiscal = fiscal
                            for account in fiscal.account_ids:
                                fiscal_position[account.account_src_id.id] = account.account_dest_id.id
                elif line.order_id.config_id.discount_promotion_bundle_id.id == line.product_id.id \
                        or line.order_id.config_id.discount_promotion_product_id.id == line.product_id.id \
                        or line.order_id.config_id.discount_product_id.id == line.product_id.id:
                    if iindex > 0:
                        pre_line = order.lines[iindex - 1]
                        if pre_line.promotion_ids:
                            for promotion in pre_line.promotion_ids:
                                for fiscal in promotion.fiscal_position_ids:
                                    for account in fiscal.account_ids:
                                        fiscal_position[account.account_src_id.id] = account.account_dest_id.id
                else:
                    if line.order_id.fiscal_position_id:
                        for account in line.order_id.fiscal_position_id.account_ids:
                            fiscal_position[account.account_src_id.id] = account.account_dest_id.id
                if fiscal_position:
                    if income_account in fiscal_position:
                        income_account = fiscal_position[income_account]
                name = line.product_id.name
                if line.notice:
                    # add discount reason in move
                    name = name + ' (' + line.notice + ')'

                # Create a move for the line for the order line
                insert_data('product', self.get_product_value(cr, uid, income_account, name, amount, order, line, context))

                # Create the tax lines
                taxes = []
                for t in line.tax_ids_after_fiscal_position:
                    if t.company_id.id == current_company.id:
                        taxes.append(t.id)
                if not taxes:
                    continue
                for tax in account_tax_obj.browse(cr, uid, taxes, context=context).compute_all(line.price_unit * (100.0 - line.discount) / 100.0, cur, line.qty)['taxes']:
                    insert_data('tax', self.get_tax_value(cr, uid, income_account, tax, order, line))
                iindex += 1
            fiscal_position = {}
            # if order.fiscal_position_id:
            if order_fiscal:
                for account in order_fiscal.account_ids:
                    fiscal_position[account.account_src_id.id] = account.account_dest_id.id
            if fiscal_position:
                if order_account in fiscal_position:
                    order_account = fiscal_position[order_account]

            # counterpart
            insert_data('counter_part', self.get_counterpart_value(cr, uid, order, order_account))

            order.write({'state': 'done', 'account_move': move_id})

        all_lines = []
        first_order = self.browse(cr, uid, ids[0], context=context)
        for group_key, group_data in grouped_data.iteritems():
            for value in group_data:
                # TruongNN
                analytic_account_id = first_order.outlet_id and first_order.outlet_id.analytic_account_id and first_order.outlet_id.analytic_account_id.id or False
                value.update({
                    'analytic_account_id': analytic_account_id
                })
                # TruongNN
                all_lines.append((0, 0, value), )
        if move_id:  # In case no order was changed
            self.pool.get("account.move").write(cr, uid, [move_id], {'line_ids': all_lines}, context=dict(context or {}, dont_create_taxes=True))
            self.pool.get("account.move").post(cr, uid, [move_id], context=context)

        return True

    def get_tax_value(self, cr, uid, income_account, tax, order, orderline):
        return {
            'name': _('Tax') + ' ' + tax['name'],
            'product_id': orderline.product_id.id,
            'quantity': orderline.qty,
            'account_id': tax['account_id'] or income_account,
            'credit': ((tax['amount'] > 0) and tax['amount']) or 0.0,
            'debit': ((tax['amount'] < 0) and -tax['amount']) or 0.0,
            'tax_line_id': tax['id'],
            'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(order.partner_id).id or False,
            'analytic_account_id': (False,)
        }

    def get_product_value(self, cr, uid, income_account, name, amount, order, line, context):
        return {
            'name': name,
            'quantity': line.qty,
            'product_id': line.product_id.id,
            'account_id': income_account,
            'analytic_account_id': self._prepare_analytic_account(cr, uid, line, context=context),
            'credit': ((amount > 0) and amount) or 0.0,
            'debit': ((amount < 0) and -amount) or 0.0,
            'tax_ids': [(6, 0, line.tax_ids.ids)],
            'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(order.partner_id).id or False
        }

    def get_counterpart_value(self, cr, uid, order, order_account):
        return {
            'name': _("Trade Receivables"),  # order.name,
            'account_id': order_account,
            'credit': ((order.amount_total < 0) and -order.amount_total) or 0.0,
            'debit': ((order.amount_total > 0) and order.amount_total) or 0.0,
            'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(order.partner_id).id or False,
            'analytic_account_id': (False,)
        }

    def set_grouped_line(self, current_value, values):
        current_value['quantity'] = current_value.get('quantity', 0.0) + values.get('quantity', 0.0)
        current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
        current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)