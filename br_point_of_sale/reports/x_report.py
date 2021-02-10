from openerp import models, api, fields, _
from collections import OrderedDict
from datetime import datetime, timedelta
from openerp.exceptions import ValidationError, UserError
from openerp.tools import float_round
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
PRECISION = 2




class DISCOUNT_TYPE(object):
    BILL = 1
    PRODUCT = 2
    BUNDLE = 3


class PosSession(models.Model):
    _inherit = "pos.session"

    no_of_printed = fields.Integer(string="Times Printed", default=0)
    # number printed for Pre Closing Report
    pre_closing_no_of_printed = fields.Integer(string="Times Printed", default=0)

    @api.model
    def get_date(self, str_date):
        return datetime.strptime(str_date, DATE_FORMAT) #+ timedelta(hours=8)

    # @api.model
    # def prepare_domain_stock_transfers(self, start_date, end_date, pos_session):
    #     return ['&', '&', ('picking_type_code', 'in', ['incoming']),
    #             ('location_dest_id', '=', pos_session.outlet_id.warehouse_id.lot_stock_id.id),
    #             '|', '&', ('min_date', '<', str(end_date)), ('state', 'not in', ['done', 'cancel', 'draft']),
    #             '&', ('min_date', '>=', str(start_date)), ('min_date', '<=', str(end_date))]
    @api.model
    def prepare_domain_stock_transfers(self, start_date, end_date, pos_session):
        return ['&',

                '&',
                ('picking_type_code', 'in', ['incoming','internal']),

                '|',
                ('location_dest_id', '=', pos_session.outlet_id.warehouse_id.lot_stock_id.id),
                ('location_id', '=', pos_session.outlet_id.warehouse_id.lot_stock_id.id),
                #'|',
                #'&',
                #('min_date', '<', str(end_date)),
                #('state', 'not in', ['done', 'cancel', 'draft']),
                '&',
                ('min_date', '>=', str(start_date)),
                ('min_date', '<=', str(end_date))]

    @api.multi
    def get_stock_transfers(self):
        stock_transfer_obj = self.env['stock.picking']
        picking_state = getattr(stock_transfer_obj, '_fields')['state'].selection
        result = {}

        def get_state(state_key):
            state_string = [option[1] for option in picking_state if option[0] == state_key]
            if len(state_string):
                return state_string[0]
            return state_key
        for pos_session in self:
            session_date = datetime.strptime(pos_session.start_at, DATE_FORMAT)
            start_date = session_date.replace(hour=0, minute=0, second=0) - timedelta(hours=8)
            end_date = session_date.replace(hour=23, minute=59,second=59) - timedelta(hours=8)
            data = stock_transfer_obj.search(self.prepare_domain_stock_transfers(start_date,
                                                                                 end_date, pos_session), order='min_date')

            #print "domain",self.prepare_domain_stock_transfers(start_date,end_date, pos_session)
            #print "data>>>>>>>>",data

            result[pos_session.id] = [{"min_date": self.get_date(x.min_date).strftime(DATE_FORMAT),
                                       "name": x.name, "state": get_state(x.state)} for x in data]
        return result

    @api.multi
    def get_x_report_data(self):
        # FIXME: wise one, please help to refactor this function ...
        if self[0].state != 'closed' and not self._context.get('rp_name', False):
            raise ValidationError(_("BRReportMessage: You can only print X Report when session is already closed and posted!"))
            # return {"type": "report_message", "report_message": "Can only print closed session !"}
        len_sessions = len(self)
        total_sale = total_net_sale = ticket_count = cancelled_receipt_amount = cash_purchase = non_cash = cash_var = gst = tax_adj = rounding_total = 0
        rp_name = ''
        if self._context.get('rp_name', False) == 'pre_closing':
            report_name = 'Pre-closing Report'
            rp_name = self._context.get('rp_name')
        else:
            if self.env.context.get('active_model', '') == 'z.report':
                report_name = 'Z Report'
            else:
                report_name = 'X Report'
        total_order = 0
        total_on_site = 0
        all_cancelled_receipt = []
        sessions = []
        all_payments = {}
        all_payment_types = {}
        all_payment_types_with_rounding = {'all_total':0.0}
        sale_insentive_ticket_count = {'on_off_site': 0 , 'on_off_redemption':0}
        payment_modes = []
        menus = {}
        discounts = {}
        cash_controls = {}
        cash_controls_grouped = {}
        none_sales = {}
        gst_dict = {}
        vouchers_str = ""
        rounding_product = self.env.user.company_id.rounding_product_id.id
        # Cache all pos category with ancestor as value
        menu_category = self.env['br.menu.category']
        menu_categs_parent = menu_category.search([('parent_id', '=', None)])
        menu_categs_cache = {}
        cancelled_receipt_lst = []
        for parent in menu_categs_parent:
            children = menu_category.search([('id', 'child_of', parent.id)])
            for child in children:
                menu_categs_cache[child.id] = parent.name

        # Get opening/closing balance
        first_session = self[0]
        last_session = self[len_sessions - 1]
        if last_session.state == 'closed':
            theoretical_closing_balance = last_session.posted_cash_register_balance_end
        else:
            theoretical_closing_balance = last_session.cash_register_balance_end
        if len_sessions > 1:
            prev_diff_amount = sum([x.posted_cash_register_difference for x in self[0:len_sessions-1]])
            theoretical_closing_balance -= prev_diff_amount
        cash_register_balance_end_real = last_session.cash_register_balance_end_real
        cash_register_balance_start = first_session.cash_register_balance_start
        adjustment = {
            'qty': 0,
            'sales': 0
        }
        for session in self:
            cash_var += (session.cash_register_balance_end_real - (session.posted_cash_register_balance_end or session.cash_register_balance_end))
            sessions.append(session)
            orders = self.env['pos.order'].search([('session_id', '=', session.id)], order='date_order')
            pos_config = session.config_id

            discount_products = [pos_config.discount_product_id.id,
                                 pos_config.discount_promotion_bundle_id.id,
                                 pos_config.discount_promotion_product_id.id]
            payment_modes.extend([x.journal_id.name for x in session.statement_ids if x.journal_id.type != 'cash'])
            for order in orders:
                if len(order.lines.filtered(lambda x: x.non_sale)) > 0:
                    is_non_sale = True
                else:
                    is_non_sale = False
                # Get sales amount and promotion from pos order line
                sale = 0
                net_sale = 0
                is_ticket = True
                none_sales[order.id] = {}
                traveled_promotions = []
                master_line_traveled = []
                for orderline in order.lines:
                    for tax in orderline.tax_ids_after_fiscal_position:
                        if order.id not in gst_dict:
                            gst_dict[order.id] = {}
                        if tax not in gst_dict[order.id]:
                            gst_dict[order.id][tax] = [float_round(orderline.price_unit * orderline.qty, PRECISION)]
                        else:
                            gst_dict[order.id][tax].append(float_round(orderline.price_unit * orderline.qty, PRECISION))
                    # Group all rounding orderlines into Adjustment menu
                    if orderline.product_id.id == rounding_product:
                        adjustment["qty"] += orderline.qty
                        adjustment["sales"] += orderline.price_subtotal
                    sale += orderline.price_subtotal_incl
                    net_sale += orderline.price_subtotal
                    for promotion in orderline.promotion_ids:
                        if promotion.is_non_sale_trans:
                            is_ticket = False
                            if orderline.master_id and orderline.master_id.id not in master_line_traveled:
                                if promotion.name in none_sales[order.id]:
                                    if orderline.menu_name_id.name_template in none_sales[order.id][promotion.name]['products']:
                                        none_sales[order.id][promotion.name]['products'][orderline.menu_name_id.name_template] += orderline.master_id.qty
                                    else:
                                        none_sales[order.id][promotion.name]['products'][orderline.menu_name_id.name_template] = orderline.master_id.qty
                                else:
                                    date_order = datetime.strptime(order.date_order, DATE_FORMAT) + timedelta(hours=8)
                                    none_sales[order.id][promotion.name] = {
                                        'products': {
                                            orderline.menu_name_id.name_template: orderline.master_id.qty
                                        },
                                        'note': u'"%s | %s | %s | %s' % (order.name, date_order.strftime(DATE_FORMAT), orderline.user_promotion.partner_id.name[:30] if orderline.user_promotion and orderline.user_promotion.partner_id else "", order.note[:100])
                                    }
                            master_line_traveled.append(orderline.master_id.id)
                        elif orderline.product_id.id not in discount_products:
                            """
                            Count times that promotion is utilised
                            E.g:
                            Product discount: 1 time apply discount button = 1 product
                            Bundle discount: 1 time apply discount button can be more than 1 product
                            Bill discount: 1 time apply discount button = 1 receipt
                            """

                            if not promotion.is_hq_voucher:
                                promotion_name = promotion.name
                                if promotion_name in discounts:
                                    if promotion.id not in traveled_promotions:
                                        if promotion.type_promotion != DISCOUNT_TYPE.BILL:
                                            discounts[promotion_name]['rate_promotion'] += orderline.master_id.rate_promotion
                                        else:
                                            discounts[promotion_name]['rate_promotion'] += 1 * (not order.is_refund or -1)
                                    discounts[promotion_name]['amount'] += orderline.discount_amount
                                else:
                                    discounts[promotion_name] = {
                                        'qty': 1,
                                        'amount': orderline.discount_amount,
                                        'rate_promotion': orderline.master_id.rate_promotion if promotion.type_promotion != DISCOUNT_TYPE.BILL else 1 * (not order.is_refund or -1),
                                        'vouchers': []
                                    }
                            traveled_promotions.append(promotion.id)
                adjustment["sales"] -= order.tax_adjustment
                tax_adj += order.tax_adjustment
                # Get all payment from statements, exclude none sales and cancel receipt
                payments = {}
                for stm in order.statement_ids.sorted(key=lambda x: (x.journal_id.sequence, x.journal_id.name)):
                    # if stm.journal_id.type != 'cash':
                    #     non_cash['amount'] += stm.amount
                    #     non_cash['qty'] += 1
                    if stm.journal_id.type == 'cash' and not stm.journal_id.is_rounding_method:
                        cash_purchase += stm.amount
                    journal_name = stm.journal_id.name
                    if stm.journal_id.is_rounding_method:
                        rounding_total += stm.amount
                    if not stm.journal_id.is_rounding_method:
                        if order.is_refund:
                            py_qty = -1
                        else:
                            py_qty = 1
                        if journal_name in all_payments:
                            all_payments[journal_name]['amount'] += stm.amount
                            if journal_name not in payments:
                                all_payments[journal_name]['qty'] += py_qty
                        else:
                            if rp_name != 'pre_closing':
                                all_payments[journal_name] = {'amount': stm.amount,
                                                              'qty': py_qty}
                            elif stm.journal_id.type != 'cash' and not stm.journal_id.is_rounding_method:
                                all_payments[journal_name] = {'amount': stm.amount,
                                                              'qty': py_qty}
                    if journal_name in payments:
                        payments[journal_name] += stm.amount
                    else:
                        payments[journal_name] = stm.amount

                # check payment method != on_site
                total_on_site_by_order = 0
                have_onsite = False
                total_payment = 0
                for stm in order.statement_ids:
                    if stm.journal_id.payment_type == 'on_site':
                        total_on_site_by_order += stm.amount
                        have_onsite = True
                    total_payment += stm.amount



                #comment bellow code as it affect on megascoop sale where only offsite sale without rounding 
                # if not have_onsite:
                #     is_ticket = False

                is_refund_or_refunded = False
                if order.is_refund or order.is_refunded:
                    is_ticket = False
                    is_refund_or_refunded = True
                    if order.is_refund:
                        remark = str(order.note.encode("utf-8"))
                        cancelled_receipt = "{receipt_no} | {amount} | {payment_mode} | {remark}".format(
                            receipt_no=order.pos_reference,
                            amount=sale,
                            payment_mode="|".join(payments.keys()),
                            remark=remark
                        )
                        all_cancelled_receipt.append(cancelled_receipt)
                        cancelled_receipt_lst.append({
                            'receipt_no': order.pos_reference,
                            'amount': sale,
                            'payment_mode': "|".join(payments.keys()),
                            'remark': remark
                        })
                        cancelled_receipt_amount += sale
                if order.is_refund or order.is_refunded:
                    pass
                else:
                    total_order += 1

                proceed_order_payment = []
                proceed_order_sale_insentive_on_off_tc = []
                proceed_order_insentive_on_off_redem_tc = []
                for stm in order.statement_ids:
                    # if (not order.is_refund or not order.is_refunded) and not stm.journal_id.is_rounding_method:
                    # if not is_refund_or_refunded:
                    if not is_non_sale:
                        #if is_ticket and not stm.journal_id.is_rounding_method:
                        if order.is_refund:
                            tc_qty = -1
                        else:
                            tc_qty = 1
                        if not stm.journal_id.is_rounding_method:
                            # for onsite offsite block
                            if stm.journal_id.payment_type not in all_payment_types:

                                all_payment_types[stm.journal_id.payment_type] = {'amount': stm.amount, 'qty': tc_qty}
                                if stm.journal_id.payment_type not in proceed_order_payment:
                                    proceed_order_payment.append(stm.journal_id.payment_type)
                            else:
                                if stm.journal_id.payment_type not in proceed_order_payment:
                                    proceed_order_payment.append(stm.journal_id.payment_type)
                                    all_payment_types[stm.journal_id.payment_type]['amount'] += stm.amount
                                    all_payment_types[stm.journal_id.payment_type]['qty'] += tc_qty
                                else:
                                    all_payment_types[stm.journal_id.payment_type]['amount'] += stm.amount

                            # for sale and incentive ticket count
                            if stm.journal_id.payment_type in ['on_site','off_site'] and stm.journal_id.payment_type not in proceed_order_sale_insentive_on_off_tc:
                                sale_insentive_ticket_count['on_off_site'] += tc_qty
                                proceed_order_sale_insentive_on_off_tc.append('on_site')
                                proceed_order_sale_insentive_on_off_tc.append('off_site')
                            if stm.journal_id.payment_type in ['on_site','off_site', 'redemption'] and stm.journal_id.payment_type not in proceed_order_insentive_on_off_redem_tc:
                                sale_insentive_ticket_count['on_off_redemption'] += tc_qty
                                proceed_order_insentive_on_off_redem_tc.append('redemption')
                                proceed_order_insentive_on_off_redem_tc.append('on_site')
                                proceed_order_insentive_on_off_redem_tc.append('off_site')

                        # for onsite offsite with rounding
                        if stm.journal_id.payment_type not in all_payment_types_with_rounding:
                            all_payment_types_with_rounding[stm.journal_id.payment_type] = stm.amount
                        else:
                            all_payment_types_with_rounding[stm.journal_id.payment_type] += stm.amount
                        all_payment_types_with_rounding['all_total'] += stm.amount

                # Get vouchers
                if order.vouchers:
                    vouchers_str += order.vouchers

                if is_ticket:
                    # Count tickets when order is not none sale or cancelled receipt
                    ticket_count += 1
                    # Count menu name

                for menu in order.master_ids:
                    if menu.product_id.menu_category_id:
                        categ_name = menu_categs_cache[menu.product_id.menu_category_id.id]
                        sale_amount = 0
                        for line in menu.order_lines:
                            sale_amount += (line.price_subtotal_incl - line.discount_amount)
                            tax_on_gst = 0
                            for tax in line.tax_ids_after_fiscal_position:
                                if tax.price_include:
                                    sale_amount -= float_round(round(line.qty * line.price_unit, 2) / (1 + tax.amount / 100) * (tax.amount / 100), 2)
                                    tax_on_gst += line.discount_amount / (1 + tax.amount / 100) * (tax.amount / 100)
                                else:
                                    sale_amount -= float_round(round(line.qty * line.price_unit, 2) * (tax.amount / 100), 2)
                            sale_amount += tax_on_gst
                        if total_payment:
                            sale_amount = sale_amount * total_on_site_by_order / total_payment
                        if categ_name in menus:
                            menus[categ_name]['qty'] += menu.qty
                            menus[categ_name]['sales'] += sale_amount
                        else:
                            menus[categ_name] = {'qty': menu.qty, 'sales': sale_amount}
                total_sale += sale
                total_on_site += total_on_site_by_order

            voucher_codes = vouchers_str.split(";")
            vouchers = self.env['br.config.voucher'].search([('voucher_code', 'in', voucher_codes)])
            for voucher in vouchers.sorted(key=lambda x: x.promotion_id.name):
                promotion_name = voucher.promotion_id.name
                if promotion_name in discounts:
                    discounts[promotion_name]['vouchers'].append(voucher.voucher_code)

            statement_lines = session.cash_register_id.line_ids.filtered(lambda o: o.cash_control_id)
            statement_lines = sorted(statement_lines, key=lambda x: (x.cash_control_id.action == 'put_in' and -8 or 0) + (x.cash_control_id.action == 'failed_bank_in' and -4 or 0) + (x.cash_control_id.action == 'take_out' and -2 or 0) + (x.cash_control_id.action == 'bank_in' and -1 or 0))
            for stmline in statement_lines:
                cc_key = stmline.cash_control_id.name + str(stmline.id)
                cash_controls[cc_key] = {
                    'amount': stmline.amount,
                    'name': stmline.cash_control_id.name,
                    'remark': stmline.name.split(":")[-1],
                    'action': 'in' if stmline.cash_control_id.action in ('put_in', 'failed_bank_in') else 'out'
                }
                # Group statement line by name
                if stmline.cash_control_id.id in cash_controls_grouped:
                    cash_controls_grouped[stmline.cash_control_id.id]['count'] += 1
                    cash_controls_grouped[stmline.cash_control_id.id]['amount'] += stmline.amount
                else:
                    cash_controls_grouped[stmline.cash_control_id.id] = {
                        'amount': stmline.amount,
                        'name': stmline.cash_control_id.name,
                        'remark': stmline.name.split(":")[-1],
                        'action': 'in' if stmline.cash_control_id.action in ('put_in', 'failed_bank_in') else 'out',
                        'count': 1
                    }

            # Count printed times
            if self.env.context.get('active_model', '') != 'z.report' and rp_name != 'pre_closing':
                session.no_of_printed += 1
            if rp_name == 'pre_closing':
                session.pre_closing_no_of_printed += 1

        for order_id in gst_dict:
            gst_per_order = 0
            for tax in gst_dict[order_id]:
                for total_price in gst_dict[order_id][tax]:
                    if tax.price_include:
                        gst_per_order += float_round(total_price / (1 + tax.amount / 100) * (tax.amount / 100), 2)
                    else:
                        gst_per_order += float_round(total_price * (tax.amount / 100), 2)
            gst += float_round(gst_per_order, 2)
        menus = OrderedDict(sorted(menus.items()))
        menus["Adjustment"] = adjustment
        menus["Rounding"] = {'qty': 0.0, 'sales': rounding_total * -1}
        # NOTE: this bellow line is for adding rounding value to in total sales as we remove rounding printing saperatly in report
        total_sale = total_sale + (rounding_total * -1)
        total_on_site = total_on_site + (rounding_total * -1)
        gst += tax_adj

        total_net_sale = total_sale - gst
        net_on_site_excl_tax = 0.0
        net_off_site_excl_tax = 0.0
        net_redemption_site_excl_tax = 0.0

        if all_payment_types_with_rounding.get('all_total') and all_payment_types_with_rounding['all_total'] != 0:
            net_on_site_excl_tax = float_round((all_payment_types_with_rounding.get('on_site') and all_payment_types_with_rounding['on_site'] or 0.0) / all_payment_types_with_rounding['all_total'] * total_net_sale, 2)
            net_off_site_excl_tax = float_round( (all_payment_types_with_rounding.get('off_site') and all_payment_types_with_rounding['off_site'] or 0.0) / all_payment_types_with_rounding['all_total'] * total_net_sale, 2 )
            net_redemption_site_excl_tax = float_round( (all_payment_types_with_rounding.get('redemption') and all_payment_types_with_rounding['redemption'] or 0.0) / all_payment_types_with_rounding['all_total'] * total_net_sale, 2 )

        on_ticket_avg = 0.0
        off_ticket_avg = 0.0
        redumption_ticket_avg = 0.0
        if all_payment_types.get('on_site'):
            on_ticket_avg = float_round( net_on_site_excl_tax / (all_payment_types['on_site']['qty'] or 1), 2)
        if all_payment_types.get('off_site'):
            off_ticket_avg = float_round( net_off_site_excl_tax / (all_payment_types['off_site']['qty'] or 1) , 2)
        if all_payment_types.get('redemption'):
            redumption_ticket_avg = float_round( net_redemption_site_excl_tax / (all_payment_types['redemption']['qty'] or 1), 2)

        return {
            'report_name': report_name,
            'sessions': sessions,
            'theoretical_closing_balance': theoretical_closing_balance,
            'cash_register_balance_end_real': cash_register_balance_end_real,
            'cash_register_balance_start': cash_register_balance_start,
            'cash_var': cash_var,
            'total_sale': total_sale,
            'total_net_sale': total_sale - gst,
            'gst': gst,
            'ticket_count': ticket_count,
            'ticket_avg': float_round(float(total_sale - gst) / ticket_count, 2) if ticket_count else 0,
            'cancelled_receipt_count': len(all_cancelled_receipt),
            'cancelled_receipt_amount': cancelled_receipt_amount,
            'all_cancelled_receipt': sorted(all_cancelled_receipt),
            'payment_modes': payment_modes,
            'all_payments': all_payments,
            'all_payment_types': all_payment_types,
            'all_payment_types_on_site_amount' : all_payment_types.get('on_site') and float_round(all_payment_types['on_site']['amount'],2) or 0.0,
            'all_payment_types_on_site_qty': all_payment_types.get('on_site') and all_payment_types['on_site']['qty'] or 0,
            'all_payment_types_off_site_amount': all_payment_types.get('off_site') and float_round(all_payment_types['off_site']['amount'],2) or 0.0,
            'all_payment_types_off_site_qty': all_payment_types.get('off_site') and all_payment_types['off_site']['qty'] or 0,
            'all_payment_types_redemption_amount': all_payment_types.get('redemption') and float_round(all_payment_types['redemption']['amount'],2) or 0.0,
            'all_payment_types_redemption_qty': all_payment_types.get('redemption') and all_payment_types['redemption']['qty'] or 0,
            'cash_purchase': cash_purchase,
            # 'non_cash': non_cash,
            'rp_name': rp_name,
            'menus': menus,
            'cash_controls': OrderedDict(sorted(cash_controls.items())),
            'cash_controls_grouped': OrderedDict(sorted(cash_controls_grouped.items())),
            'none_sales': none_sales,
            'discounts': OrderedDict(sorted(discounts.items())),
            'outlet': first_session.outlet_id,
            'stock_transfers': self.get_stock_transfers(),
            'total_on_site': total_on_site,
            'cancelled_receipt_lst': cancelled_receipt_lst,
            'net_on_site_excl_tax' : net_on_site_excl_tax,
            'net_off_site_excl_tax' : net_off_site_excl_tax,
            'net_redemption_site_excl_tax' :net_redemption_site_excl_tax,
            'on_ticket_avg' : on_ticket_avg,
            'off_ticket_avg' : off_ticket_avg,
            'redumption_ticket_avg' : redumption_ticket_avg,
            'total_order':total_order,
            'sale_insentive_ticket_count': sale_insentive_ticket_count,
        }

