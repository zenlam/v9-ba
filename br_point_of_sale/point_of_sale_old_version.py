# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import tools, models, SUPERUSER_ID
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.exceptions import UserError
from datetime import date, datetime
import time
import logging
_logger = logging.getLogger(__name__)

class pos_session(osv.osv):
    _inherit = 'pos.session'

    def wkf_action_close(self, cr, uid, ids, context):
        for session in self.browse(cr, uid, ids, context=context):
            for statement in session.statement_ids:
                if (statement != session.cash_register_id) and (statement.balance_end != statement.balance_end_real):
                    self.pool.get('account.bank.statement').write(cr, uid, [statement.id], {'balance_end_real': statement.balance_end})
        return super(pos_session, self).wkf_action_close(cr, uid, ids, context)

    def _compute_cash_all(self, cr, uid, ids, fieldnames, args, context=None):
        result = dict()
        _logger.info(">>>>>HSS: OVERRIDED _compute_cash_all function")
        for record in self.browse(cr, uid, ids, context=context):
            result[record.id] = {
                'cash_journal_id' : False,
                'cash_register_id' : False,
                'cash_control' : False,
            }

            if record.config_id.cash_control:
                for st in record.statement_ids:
                    if st.journal_id.type == 'cash' and not st.journal_id.is_rounding_method:
                        result[record.id]['cash_control'] = True
                        result[record.id]['cash_journal_id'] = st.journal_id.id
                        result[record.id]['cash_register_id'] = st.id

                if not result[record.id]['cash_control']:
                    raise UserError(_("Cash control can only be applied to cash journals."))

        return result

    # TruongNN Doesn't create account move if order_ids are empty
    def _confirm_orders(self, cr, uid, ids, context=None):
        pos_order_obj = self.pool.get('pos.order')
        for session in self.browse(cr, uid, ids, context=context):
            company_id = session.config_id.journal_id.company_id.id
            local_context = dict(context or {}, force_company=company_id)
            order_ids = [order.id for order in session.order_ids if order.state == 'paid']

            # TruongNN
            if order_ids:
                move_id = pos_order_obj._create_account_move(cr, uid, session.start_at, session.name, session.config_id.journal_id.id, company_id, context=context)

                pos_order_obj._create_account_move_line(cr, uid, order_ids, session, move_id, context=local_context)
            # TruongNN

            for order in session.order_ids:
                if order.state == 'done':
                    continue
                if order.state not in ('paid', 'invoiced'):
                    raise UserError(_("You cannot confirm all orders of this session, because they have not the 'paid' status"))
                else:
                    pos_order_obj.signal_workflow(cr, uid, [order.id], 'done')

        return True

class pos_order(osv.osv):
    _inherit = "pos.order"

    _columns = {
        'pos_reference': fields.char('Invoice No', readonly=True, copy=False)
    }

    def _create_account_move_line(self, cr, uid, ids, session=None, move_id=None, context=None):
        # Tricky, via the workflow, we only have one id in the ids variable
        """Create a account move line of order grouped by products or not."""
        account_move_obj = self.pool.get('account.move')
        account_tax_obj = self.pool.get('account.tax')
        property_obj = self.pool.get('ir.property')
        cur_obj = self.pool.get('res.currency')

        #session_ids = set(order.session_id for order in self.browse(cr, uid, ids, context=context))

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
                    'move_id' : move_id,
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
                                current_value['quantity'] = current_value.get('quantity', 0.0) + values.get('quantity', 0.0)
                                current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
                                current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)
                                break
                        else:
                            grouped_data[key].append(values)
                else:
                    grouped_data[key].append(values)

            #because of the weird way the pos order is written, we need to make sure there is at least one line,
            #because just after the 'for' loop there are references to 'line' and 'income_account' variables (that
            #are set inside the for loop)
            #TOFIX: a deep refactoring of this method (and class!) is needed in order to get rid of this stupid hack
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
                    raise UserError(_('Please define income '\
                        'account for this product: "%s" (id:%d).') \
                        % (line.product_id.name, line.product_id.id))
                fiscal_position = {}
                if line.order_id.fiscal_position_id:
                    for account in line.order_id.fiscal_position_id.account_ids:
                        fiscal_position[account.account_src_id.id] = account.account_dest_id.id
                elif line.promotion_ids:
                    for promotion in line.promotion_ids:
                        for fiscal in promotion.fiscal_position_ids:
                            order_fiscal = fiscal
                            for account in fiscal.account_ids:
                                fiscal_position[account.account_src_id.id] = account.account_dest_id.id
                elif line.order_id.config_id.discount_promotion_bundle_id.id == line.product_id.id \
                        or line.order_id.config_id.discount_promotion_product_id.id == line.product_id.id \
                        or line.order_id.config_id.discount_product_id.id == line.product_id.id:
                        if iindex > 0:
                            pre_line = order.lines[iindex-1]
                            if pre_line.promotion_ids:
                                for promotion in pre_line.promotion_ids:
                                    for fiscal in promotion.fiscal_position_ids:
                                        for account in fiscal.account_ids:
                                            fiscal_position[account.account_src_id.id] = account.account_dest_id.id
                if fiscal_position:
                    if income_account in fiscal_position:
                        income_account = fiscal_position[income_account]
                name = line.product_id.name
                if line.notice:
                    # add discount reason in move
                    name = name + ' (' + line.notice + ')'

                # Create a move for the line for the order line
                insert_data('product', {
                    'name': name,
                    'quantity': line.qty,
                    'product_id': line.product_id.id,
                    'account_id': income_account,
                    'analytic_account_id': self._prepare_analytic_account(cr, uid, line, context=context),
                    'credit': ((amount>0) and amount) or 0.0,
                    'debit': ((amount<0) and -amount) or 0.0,
                    'tax_ids': [(6, 0, line.tax_ids_after_fiscal_position.ids)],
                    'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(order.partner_id).id or False
                })

                # Create the tax lines
                taxes = []
                for t in line.tax_ids_after_fiscal_position:
                    if t.company_id.id == current_company.id:
                        taxes.append(t.id)
                if not taxes:
                    continue
                for tax in account_tax_obj.browse(cr,uid, taxes, context=context).compute_all(line.price_unit * (100.0-line.discount) / 100.0, cur, line.qty)['taxes']:
                    insert_data('tax', {
                        'name': _('Tax') + ' ' + tax['name'],
                        'product_id': line.product_id.id,
                        'quantity': line.qty,
                        'account_id': tax['account_id'] or income_account,
                        'credit': ((tax['amount']>0) and tax['amount']) or 0.0,
                        'debit': ((tax['amount']<0) and -tax['amount']) or 0.0,
                        'tax_line_id': tax['id'],
                        'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(order.partner_id).id or False,
                        'analytic_account_id': (False, )
                    })
                iindex +=1
            fiscal_position = {}
            # if order.fiscal_position_id:
            if order_fiscal:
                for account in order_fiscal.account_ids:
                    fiscal_position[account.account_src_id.id] = account.account_dest_id.id
            if fiscal_position:
                if order_account in fiscal_position:
                    order_account = fiscal_position[order_account]

            # counterpart
            insert_data('counter_part', {
                'name': _("Trade Receivables"), #order.name,
                'account_id': order_account,
                'credit': ((order.amount_total < 0) and -order.amount_total) or 0.0,
                'debit': ((order.amount_total > 0) and order.amount_total) or 0.0,
                'partner_id': order.partner_id and self.pool.get("res.partner")._find_accounting_partner(order.partner_id).id or False,
                'analytic_account_id': (False, )
            })

            order.write({'state':'done', 'account_move': move_id})

        all_lines = []
        for group_key, group_data in grouped_data.iteritems():
            for value in group_data:
                # TruongNN
                first_order = self.browse(cr, uid, ids[0], context=context)
                analytic_account_id = first_order.outlet_id and first_order.outlet_id.analytic_account_id and first_order.outlet_id.analytic_account_id.id or False
                value.update({
                    'analytic_account_id': analytic_account_id
                })
                # TruongNN
                all_lines.append((0, 0, value),)
        if move_id: #In case no order was changed
            self.pool.get("account.move").write(cr, uid, [move_id], {'line_ids':all_lines}, context=dict(context or {}, dont_create_taxes=True))
            self.pool.get("account.move").post(cr, uid, [move_id], context=context)

        return True

    # Note: Override base function
    # Add Analytic Account to Picking and Journal Entry
    def create_picking(self, cr, uid, ids, context=None):
        """Create a picking for each order and validate it."""
        picking_obj = self.pool.get('stock.picking')
        partner_obj = self.pool.get('res.partner')
        move_obj = self.pool.get('stock.move')
        for order in self.browse(cr, uid, ids, context=context):
            # TruongNN
            outlet = order.outlet_id
            context = dict(context or {})
            context.update({
                'analytic_account_id':  outlet and outlet.analytic_account_id and outlet.analytic_account_id.id or False
            })
            # TruongNN
            if all(t == 'service' for t in order.lines.mapped('product_id.type')):
                continue
            addr = order.partner_id and partner_obj.address_get(cr, uid, [order.partner_id.id], ['delivery']) or {}
            picking_type = order.picking_type_id
            picking_id = False
            location_id = order.location_id.id
            if order.partner_id:
                destination_id = order.partner_id.property_stock_customer.id
            else:
                if (not picking_type) or (not picking_type.default_location_dest_id):
                    customerloc, supplierloc = self.pool['stock.warehouse']._get_partner_locations(cr, uid, [],
                                                                                                   context=context)
                    destination_id = customerloc.id
                else:
                    destination_id = picking_type.default_location_dest_id.id

            # All qties negative => Create negative
            if picking_type:
                pos_qty = all([x.qty >= 0 for x in order.lines])
                # Check negative quantities
                picking_id = picking_obj.create(cr, uid, {
                    'origin': order.name,
                    'partner_id': addr.get('delivery', False),
                    'date_done': order.date_order,
                    'min_date': order.date_order,
                    'picking_type_id': picking_type.id,
                    'company_id': order.company_id.id,
                    'move_type': 'direct',
                    'note': order.note or "",
                    'location_id': location_id if pos_qty else destination_id,
                    'location_dest_id': destination_id if pos_qty else location_id,
                }, context=context)
                self.write(cr, uid, [order.id], {'picking_id': picking_id}, context=context)

            move_list = []
            for line in order.lines:
                if line.product_id and line.product_id.type not in ['product', 'consu']:
                    continue

                move_list.append(move_obj.create(cr, uid, {
                    'name': order.session_id.name,
                    'product_uom': line.product_id.uom_id.id,
                    'picking_id': picking_id,
                    'picking_type_id': picking_type.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': abs(line.qty),
                    'state': 'draft',
                    'location_id': location_id if line.qty >= 0 else destination_id,
                    'location_dest_id': destination_id if line.qty >= 0 else location_id,
                    'date_expected': order.date_order,
                    'account_analytic_id': context.get('analytic_account_id'),
                    'pos_order_line_ref': line.name,
                }, context=context))

            if picking_id:
                picking_obj.action_confirm(cr, uid, [picking_id], context=context)
                picking_obj.force_assign(cr, uid, [picking_id], context=context)
                # Mark pack operations as done
                pick = picking_obj.browse(cr, uid, picking_id, context=context)
                self.pool['stock.picking'].action_assign(cr, uid, [picking_id], context)
                for pack in pick.pack_operation_ids:
                    self.pool['stock.pack.operation'].write(cr, uid, [pack.id], {'qty_done': pack.product_qty}, context=context)
                    if pack.product_id.tracking == 'lot':
                        total_lot_qty = 0
                        for lot in pack.pack_lot_ids:
                            self.pool['stock.pack.operation.lot'].write(cr, uid, [lot.id], {'qty': lot.qty_todo}, context=context)
                            total_lot_qty += lot.qty_todo
                        remaining_qty = pack.product_qty - total_lot_qty
                        if remaining_qty:
                            self.generate_lot_negative(cr, uid, pack.product_id, pack.id, remaining_qty)

                picking_obj.action_done(cr, uid, [picking_id], context=context)
            elif move_list:
                move_obj.action_confirm(cr, uid, move_list, context=context)
                move_obj.force_assign(cr, uid, move_list, context=context)
                move_obj.action_done(cr, uid, move_list, context=context)
        return True



    def generate_lot_negative(self, cr, uid, product, ops_id, qty):
        lot_name = 'Negative Quantity'
        new_lot_id = self.pool['stock.production.lot'].search(cr, uid, [('name', '=', lot_name),
                                                                        ('product_id', '=', product.id)], limit=1)

        if not new_lot_id:
            supplier = False
            supplier_info_id = self.pool['product.supplierinfo'].search(cr, uid, [('product_tmpl_id', '=', product.product_tmpl_id.id)
                                                                           ], limit=1)

            if supplier_info_id:
                supplier = self.pool['product.supplierinfo'].browse(cr, uid, supplier_info_id).name
            lot_vals = {
                        'product_id': product.id,
                        'name': lot_name,
                        'br_supplier_id': supplier and supplier.id or False,
                        'removal_date': datetime.now()
                        }
            new_lot_id = [self.pool['stock.production.lot'].create(cr, uid, lot_vals)]

        vals = {
            'lot_id': new_lot_id[0] or False,
            'operation_id': ops_id,
            'qty': qty
        }
        ls_op_lot_tmp = self.pool['stock.pack.operation.lot'].search(cr, uid, (
            [('lot_id', '=', new_lot_id[0]), ('operation_id', '=', ops_id)]))
        if not ls_op_lot_tmp:
            self.pool['stock.pack.operation.lot'].create(cr, uid, vals)
        else:
            neg_lot = self.pool['stock.pack.operation.lot'].browse(cr, uid, ls_op_lot_tmp)
            self.pool['stock.pack.operation.lot'].write(cr, uid, ls_op_lot_tmp, {'qty': neg_lot.qty + qty})

class stock_quant(osv.osv):
    _inherit = "stock.quant"

    # TruongNN Add analytic_account_id to Stock Journal
    def _prepare_account_move_line(self, cr, uid, move, qty, cost, credit_account_id, debit_account_id, context=None):
        """
        Generate the account.move.line values to post to track the stock valuation difference due to the
        processing of the given quant.
        """
        res = super(stock_quant, self)._prepare_account_move_line(cr, uid, move, qty, cost, credit_account_id,
                                                                  debit_account_id, context=context)
        debit_line_vals = res[0][2]
        credit_line_vals = res[1][2]
        if context is None:
            context = {}

        # TODO: add field to stock.picking that reference to pos.order.line
        query = '''
        SELECT pos_order_line.id
        FROM stock_move
          INNER JOIN stock_picking ON stock_move.picking_id = stock_picking.id
          INNER JOIN pos_order ON stock_picking.id = pos_order.picking_id
          INNER JOIN pos_order_line ON pos_order.id = pos_order_line.order_id AND pos_order_line.name = $$%s$$
        WHERE stock_move.pos_order_line_ref=$$%s$$;
        '''%(move.pos_order_line_ref, move.pos_order_line_ref)
        cr.execute(query)
        order_line_id = cr.fetchone()
        if order_line_id:
            line_obj = self.pool.get('pos.order.line').browse(cr, uid, order_line_id, context)
            if line_obj and line_obj.promotion_ids:
                fiscal_position = {}
                # fiscal_parents = [line_obj.order_id]
                fiscal_parents = []
                for promotion in line_obj.promotion_ids:
                    fiscal_parents.append(promotion)

                def create_fiscal_account_map(parent_obj):
                    for fiscal in parent_obj.fiscal_position_ids:
                        for account in fiscal.account_ids:
                            fiscal_position[account.account_src_id.id] = account.account_dest_id.id

                for obj in fiscal_parents:
                    create_fiscal_account_map(obj)
                # Map account with fiscal position's account
                if fiscal_position:
                    if debit_line_vals['account_id'] in fiscal_position:
                        debit_line_vals['account_id'] = fiscal_position[debit_line_vals['account_id']]
                    if credit_line_vals['account_id'] in fiscal_position:
                        credit_line_vals['account_id'] = fiscal_position[credit_line_vals['account_id']]

        # TruongNN
        analytic_account_id = context.get('analytic_account_id', False)
        if analytic_account_id:
            debit_line_vals.update({
                'analytic_account_id': analytic_account_id,
            })
            credit_line_vals.update({
                'analytic_account_id': analytic_account_id,
            })
            # return [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]
        # TruongNN
        res[0][2].update(debit_line_vals)
        res[1][2].update(credit_line_vals)
        return res