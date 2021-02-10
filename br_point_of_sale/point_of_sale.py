#!/usr/bin/python
# -*- encoding: utf-8 -*-

from openerp import models, fields, api, registry, _
from openerp.exceptions import UserError
import openerp.addons.decimal_precision as dp
from openerp import tools, models, SUPERUSER_ID
from functools import partial
from datetime import datetime

from openerp.tools.float_utils import float_round as round
from openerp.exceptions import ValidationError
import logging
import time

# from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, ISOLATION_LEVEL_READ_COMMITTED, \
#         ISOLATION_LEVEL_REPEATABLE_READ

# from threading import Thread
# from openerp.api import Environment
# from openerp.addons.connector.event import Event


from openerp.addons.connector.queue.job import (
    job
)

from openerp.addons.connector.session import (
    ConnectorSession
)

_logger = logging.getLogger(__name__)


@job
def _create_picking_job(session, model_name, order_id):
    order = session.env[model_name].browse(order_id)
    if order:
        if not order.picking_id:
            order.create_picking()


@job
def _action_post_job(session, model_name, order_id):
    order = session.env[model_name].browse(order_id)
    if order:
        if order.state != 'done':
            order.action_post()


class pos_order(models.Model):
    _inherit = ["pos.order"]

    invoice_no = fields.Char(string=_("Invoice No (not in use)"))
    vouchers = fields.Char(string=_("Used Vouchers"))
    time_spend = fields.Float()
    is_service_order = fields.Boolean(string="Is Service Order", help="To Check If Order includes Only Service Products", compute='_check_service_order')
    amount_untaxed = fields.Float(compute='_compute_amount_untaxed', string='Amount W/o Tax', digits=0)
    origin_total = fields.Float(string='Total before discount', digits=0)
    third_party_id = fields.Char(string="3rd Party Trans ID")

    @api.depends('statement_ids', 'lines.price_subtotal_incl', 'lines.discount')
    def _compute_amount_untaxed(self):
        for order in self:
            order.amount_paid = order.amount_return = order.amount_tax = 0.0
            currency = order.pricelist_id.currency_id
            order.amount_untaxed = currency.round(sum(line.price_subtotal for line in order.lines))


    @api.multi
    def _check_service_order(self):
        """
        Check if order includes all service product or not
        :return:
        """
        for o in self:
            o.is_service_order = all([l.product_id.type == 'service' for l in o.lines])

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if SUPERUSER_ID != self._uid and not self.env.context.get('check_duplicate_order', False):
            args.append(('outlet_id.user_ids', 'in', [self._uid]))
        return super(pos_order, self)._search(args, offset=offset, limit=limit, order=order, count=count,
                                              access_rights_uid=access_rights_uid)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if SUPERUSER_ID != self._uid:
            domain.append(('outlet_id.user_ids', 'in', [self._uid]))
        return super(pos_order, self).read_group(domain, fields, groupby, offset=offset, limit=limit, context=context,
                                                 orderby=orderby, lazy=lazy)

    @api.model
    def _default_outlet(self):
        so = self.env['pos.session']
        session_ids = so.search([('state', '=', 'opened'), ('user_id', '=', self._uid)])

        return session_ids and session_ids[0].outlet_id or False

    _defaults = {
        'user_id': lambda self, cr, uid, context: uid,
        'state': 'draft',
        'name': '/',
        'date_order': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'nb_print': 0,
        'sequence_number': 1,
        'session_id': lambda self, cr, uid, context: self._default_session(cr, uid, context),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
        'pricelist_id': lambda self, cr, uid, context: self._default_pricelist(cr, uid, context),
        'outlet_id': _default_outlet
    }

    @api.model
    def create(self, vals):
        """
        @param vals: adding values
        @return: res: pos.order object

         Since lines (pos.order.line) have master_ids (br.pos.order.line.master) but they are added to pos.order at
         the same time, at that moment master_ids is not ready for lines yet. The purpose of this function is to add
         master_id to lines

        """
        # FIXME: Should push order lines to master order lines in POS screen first,
        # the current way of adding master_id to pos order line is kind of unreliable and way too complex than it should be
        if 'refund' in self.env.context and self.env.context['refund']:
            # vals['invoice_no'] = 'REFUND ' + vals['invoice_no']
            if vals['master_ids']:
                for v in vals['master_ids']:
                    v[2]['qty'] = -v[2]['qty']
                    v[2]['rate_promotion'] = -v[2]['rate_promotion']

            if vals['lines']:
                for x in vals['lines']:
                    x[2]['qty'] = -x[2]['qty']
                    x[2]['rate_promotion'] = -x[2]['rate_promotion']
            res = super(pos_order, self).create(vals)

            # When duplicate pos.order, pos order line is still linked to old master line
            # need to update new pos.order.line with new pos.order.line.master
            master_id_by_line_master_id = {}
            for master_line in res.master_ids:
                if master_line.line_master_id:
                    master_id_by_line_master_id[master_line.line_master_id] = master_line.id

            for line in res.lines:
                if line.line_master_id in master_id_by_line_master_id and line.price_unit >= 0:
                    line.write({
                        'master_id': master_id_by_line_master_id[line.line_master_id],
                        'discount_amount': -line.discount_amount
                    })
        # Cached all line and sort them with returned id in json so children will be its parent's next line
        else:
            order_line_pool = self.env['pos.order.line']
            lines = vals['master_ids'] + vals['lines']
            amount_total_dedicate = 0
            lines_master = vals['master_ids']
            for master in lines_master:
                if master[2]['price_unit'] > 0:
                    amount_total_dedicate += master[2]['price_unit']
            # Remove these lines from "vals" so they won't be added to pos order
            _logger.info(">>>>> VALS: %s" % vals)
            del vals['master_ids']
            del vals['lines']
            res = super(pos_order, self).create(vals)
            _logger.info(">>>>>> Created: %s" % res.id)
            if lines:
                lines.sort(key=lambda x: x[2]['line_master_id'])
                order_id = res.id
                order_lines = []

                bill_promotion = False
                bill_type = 1
                bill_amount = 0
                ls_promotion_quota = []
                amount_total_promotion = 0
                config = res.config_id
                discount_product_id = config.discount_product_id.id
                discount_promotion_bundle_id = config.discount_promotion_bundle_id.id
                discount_promotion_product_id = config.discount_promotion_product_id.id
                tip_product_id = config.tip_product_id.id
                i = 0
                for item in lines:
                    # FIXME: There can be max 1 bill promotion, can we separate it from lines ?
                    if item[2]['product_id'] == discount_product_id:
                        bill_promotion = item[2]['bill_promotion_ids'][0]
                        bill_type = item[2]['bill_type']
                        bill_amount = item[2]['bill_amount']
                        # ls_promotion_quota.extend(item[2]['bill_promotion_ids'])
                    # Cash voucher
                    if 'bill_promotion_ids' in item[2] and item[2]['bill_promotion_ids']:
                        for promo_id in item[2]['bill_promotion_ids']:
                            if promo_id not in ls_promotion_quota:
                                ls_promotion_quota.append(promo_id)

                    if item[2]['product_id'] in (discount_promotion_bundle_id, discount_promotion_product_id):
                        amount_total_promotion += item[2]['price_unit']
                        if item[2]['promotion_id'] not in ls_promotion_quota:
                            ls_promotion_quota.append(item[2]['promotion_id'])
                amount_total_dedicate += amount_total_promotion

                master_order_lines = []
                tip_master_lines = []
                while i < len(lines):
                    j = i + 1
                    # If line doesn't have product_master_id then it's master line
                    if 'product_master_id' in lines[i][2] \
                            and not lines[i][2]['product_master_id'] \
                            and lines[i][2]['price_unit'] >= 0 \
                            and lines[i][2]['product_id'] not in [discount_promotion_product_id,
                                                                  discount_promotion_bundle_id,
                                                                  discount_product_id]:
                        lines[i][2].update(order_id=order_id)

                        master_order_line = lines[i]

                        lines_per_master = []
                        # Loop until next master line
                        while (j < len(lines) and (('product_master_id' in lines[j][2] and lines[j][2]['product_master_id']) or
                            lines[j][2]['product_id'] in [discount_product_id, discount_promotion_bundle_id, discount_promotion_product_id])):

                            lines[j][2].update(order_id=order_id)
                            if (lines[j][2]['price_unit']) >= 0:
                                # bg Update info promotion bill to pos order line
                                price_to_dedicate = lines[j][2]['price_unit'] * lines[j][2]['qty']
                                pre_discount_amount = 0
                                cur_discount_amount = 0
                                ls_promotion = []

                                if 'discount_amount' in lines[j][2] and lines[j][2]['discount_amount']:
                                    pre_discount_amount = lines[j][2]['discount_amount']
                                    price_to_dedicate = price_to_dedicate - pre_discount_amount
                                if 'promotion_id' in lines[j][2] and lines[j][2]['promotion_id']:
                                    ls_promotion.append(lines[j][2]['promotion_id'])
                                    if lines[j][2]['promotion_id'] not in ls_promotion_quota:
                                        ls_promotion_quota.append(lines[j][2]['promotion_id'])
                                if bill_promotion:
                                    if bill_type == 1:  # bill promotion by percentage
                                        cur_discount_amount = pre_discount_amount + round(
                                            float(price_to_dedicate * bill_amount) / float(100), 2)
                                    else:
                                        if amount_total_dedicate > 0:
                                            cur_discount_amount = pre_discount_amount + round(
                                                float(price_to_dedicate * bill_amount) / float(amount_total_dedicate),
                                                2)
                                    if lines[j][2]['product_id'] == tip_product_id:
                                        cur_discount_amount = 0
                                        # ls_promotion = []
                                    lines[j][2].update(
                                        discount_amount=cur_discount_amount
                                    )
                                if 'bill_promotion_ids' in lines[j][2] and lines[j][2]['bill_promotion_ids']:
                                    for promo_id in lines[j][2]['bill_promotion_ids']:
                                        if promo_id not in ls_promotion:
                                            ls_promotion.append(promo_id)
                                # Update ls promotion
                                if ls_promotion:
                                    lines[j][2].update(promotion_ids=[(6, 0, ls_promotion)])

                            # If line is bill promotion then it's not belong to any master line
                            if lines[j][2]['product_id'] in [discount_product_id, discount_promotion_bundle_id,
                                                             discount_promotion_product_id, tip_product_id]:
                                if lines[j][2]['product_id'] == tip_product_id:
                                    lines[j][2].update(promotion_ids=[(6, 0, ls_promotion_quota)])
                                elif lines[j][2]['promotion_id']:
                                    lines[j][2].update(promotion_ids=[(6, 0, [lines[j][2]['promotion_id']])])
                                l = order_line_pool.create(lines[j][2])
                                # Create menu order line for tip product
                                if lines[j][2]['product_id'] == tip_product_id:
                                    tip_master_line = list(lines[j])
                                    # tip product's line_master_id is closest menu line's line_master_id (shouldn't be like that)
                                    # update line_master_id to -1 to avoid confuse between tip product and menu line
                                    tip_master_line[2].update(
                                        order_lines=[(4, l.id)],
                                        line_master_id=-1,
                                    )
                                    tip_master_lines.append(tip_master_line)
                            else:
                                lines_per_master.append(lines[j])
                            # ed Update info promotion bill to pos order line
                            order_lines.append(lines[j])
                            j += 1
                        master_order_line[2].update(order_lines=lines_per_master)
                        master_order_lines.append(master_order_line)
                    i = j

                if tip_master_lines:
                    master_order_lines.extend(tip_master_lines)
                # Update order lines
                res.write({'master_ids': master_order_lines})
                # update quota and user quota
                res.update_quota(vals['outlet_id'], ls_promotion_quota, order_lines, master_order_lines)
        return res

    def update_quota(self, outlet_id, ls_promotion_quota, order_lines, master_order_lines):
        promotion_obj = self.env['br.bundle.promotion'].browse(ls_promotion_quota)
        for iindex in range(0, len(promotion_obj)):
            promotion = promotion_obj[iindex]
            # if promotion.type_promotion == 1:
            # lines = [x for x in order_lines if 'promotion_ids' in x[2] and (6, 0,[promotion.id]) in x[2]['promotion_ids']]
            # else:
            lines = list(
                filter(lambda x: 'promotion_ids' in x[2] and promotion.id in x[2]['promotion_ids'][0][2], order_lines))
            quota_type = promotion.quota_type
            user_quota_type = promotion.user_quota_type
            # Update quota number for all outlets in promotion
            if lines:
                # For OUTLET QUOTA
                if quota_type:
                    outlet_quota = self.env['br.promotion.outlet.quota'].search(
                        [('outlet_id', '=', outlet_id),
                         ('promotion_id', '=', promotion.id)])
                    num_cur_used = 1
                    if lines[0][2]['rate_promotion']:
                        num_cur_used = lines[0][2]['rate_promotion']
                    outlet_quota.write({'used_quota': outlet_quota.used_quota + num_cur_used})
                    if promotion.quota_type == 'global':
                        promotion.write({'used_quota': promotion.used_quota + num_cur_used})

                # For USER QUOTA
                if user_quota_type:
                    if lines[0][2]['user_promotion']:
                        user_quota = self.env['br.promotion.user.quota'].search(
                            [('user_id', '=', int(lines[0][2]['user_promotion'])),
                             ('promotion_id', '=', promotion.id)])
                        num_cur_used = 1
                        if lines[0][2]['rate_promotion']:
                            num_cur_used = lines[0][2]['rate_promotion']
                        if user_quota_type == 'quantity':
                            user_quota.write({'used_quota': user_quota.used_quota + num_cur_used})
                        if user_quota_type == 'amount':
                            user_quota.write({'used_quota': user_quota.used_quota + self.origin_total})

    @api.model
    def _order_fields(self, ui_order):
        # FIXME: Why not separate master and order line first ?
        process_master = partial(self.env['pos.order.line']._order_master_fields)
        process_line = partial(self.env['pos.order.line']._order_line_fields)
        lines = []
        master_lines = []
        master_id = 0
        if ui_order['lines']:
            for l in ui_order['lines']:
                if process_master(l):
                    master_lines.append(l)
                    l[2]['line_master_id'] = l[2]['id']
                    master_id = l[2]['id']
                # We assume the next line of master line is flavour line, this method is kind of unreliable tho ...
                if process_line(l):
                    l[2]['line_master_id'] = master_id
                    lines.append(l)

        return {
            'name': ui_order['name'],
            'user_id': ui_order['user_id'] or False,
            'session_id': ui_order['pos_session_id'],
            'lines': lines,
            'master_ids': master_lines,
            'pos_reference': ui_order['name'],
            'partner_id': ui_order['partner_id'] or False,
            'date_order': ui_order['creation_date'],
            'fiscal_position_id': ui_order['fiscal_position_id'],
            'outlet_id': ui_order['outlet_id'],
            'note': ui_order['note'] if 'note' in ui_order else '',
            'vouchers': ", ".join(ui_order['use_voucher']),
            'time_spend': ui_order['time_spend'] or 0,
            'origin_total': ui_order['origin_total'] or 0,
            'third_party_id': ui_order.get('third_party_id') or '',
            # invoice_no isn't used anymore
            # 'invoice_no': ui_order['invoice_no']
        }

    def _get_valid_session(self, cr, uid, order, context=None):
        session = self.pool.get('pos.session')
        closed_session = session.browse(cr, uid, order['pos_session_id'], context=context)

        # Find existing rescue session or else create new one
        existing_rescue = session.search(cr, uid, [('state', '=', 'opened'),
                                                   ('config_id', '=', closed_session.config_id.id),
                                                   ('rescue', '=', True)],
                                         limit=1, order="start_at DESC", context=context)
        if existing_rescue:
            return existing_rescue[0]

        _logger.warning('session %s (ID: %s) was closed but received order %s (total: %s) belonging to it',
                        closed_session.name,
                        closed_session.id,
                        order['name'],
                        order['amount_total'])
        _logger.warning('attempting to create recovery session for saving order %s', order['name'])
        new_session_id = session.create(cr, uid, {
            'config_id': closed_session.config_id.id,
            'outlet_id': closed_session.outlet_id.id,
            'pricelist_id': closed_session.outlet_id.id,
            'name': _('(RESCUE FOR %(session)s)') % {'session': closed_session.name},
            'rescue': True,  # avoid conflict with live sessions
        }, context=context)
        new_session = session.browse(cr, uid, new_session_id, context=context)

        # bypass opening_control (necessary when using cash control)
        new_session.signal_workflow('open')
        return new_session_id

    @api.model
    def _process_order(self, ui_order):
        res = super(pos_order, self)._process_order(ui_order)

        # Vannh Begin Update lai status khi voucher da dc dung
        order = self.browse(res)
        # products = [x.product_id.id for x in order.lines]
        # config = order.config_id
        # discount_promotion_product_id = config.discount_promotion_product_id.id
        # discount_product_id = config.discount_product_id.id
        # discount_promotion_bundle_id = config.discount_promotion_bundle_id.id
        # if (discount_product_id in products) \
        #         or (discount_promotion_bundle_id in products) \
        #         or (discount_promotion_product_id in products) \
        #         or (order.lines and order.lines[0].non_sale):
        if 'use_voucher' in ui_order and ui_order['use_voucher']:
            ls_voucher_code = ui_order['use_voucher']
            for voucher_code in ls_voucher_code:
                voucher = self.env['br.config.voucher'].search([('voucher_validation_code', '=', voucher_code)], limit=1)
                voucher.write({'status': 'redeemed', 'date_red': datetime.now(), 'order_id': res})
        # End Begin Update lai status khi voucher da dc dung

        company = self.env.user.company_id
        # prec = 2 to avoid floating point
        rounding = round(order.amount_paid - order.amount_total, 2)
        if rounding:
            rounding_product = company.rounding_product_id or False
            if not rounding_product:
                raise UserWarning(_("Your company didn't config rounding product"))
            taxes = rounding_product.taxes_id.filtered(lambda x: x.company_id.id == company.id)
            rounding_tax = taxes and taxes[0] or False
            if rounding_tax and not rounding_tax.price_include:
                rounding = rounding / (1 + rounding_tax.amount / 100)
            rounding_order_line = {
                'order_id': order.id,
                'product_id': rounding_product.id,
                'qty': 1,
                'tax_ids': [(6, 0, [tax.id for tax in rounding_product.taxes_id if
                                    tax.company_id == company])] if rounding_product.taxes_id else False,
                'price_unit': rounding,
                'discount_amount': 0
            }
            self.env['pos.order.line'].create(rounding_order_line)
        # config.write({'sequence_number': config.sequence_number + 1})
        return res

    master_ids = fields.One2many('br.pos.order.line.master', 'order_id', string="Menu Name Line",
                                 states={'draft': [('readonly', False)]},
                                 readonly=True, copy=True)

    @api.multi
    def action_post(self):
        for order in self:
            if order.state == 'done':
                continue
            if order.state not in ('paid', 'invoiced'):
                raise UserError(
                    _("You cannot confirm all orders, because they have not the 'paid' status"))
            else:
                # T4436 Move state of order to post automatically after validating transaction
                company_id = order.session_id.config_id.journal_id.company_id.id
                session = order.session_id
                move_id = self._create_account_move(session.start_at, session.name, session.config_id.journal_id.id, company_id)
                self.with_context(force_company=company_id)._create_account_move_line(session, move_id)
                self.signal_workflow('done')

                # T4436 Create payment journal immediately after validating transaction
                statement_lines = order.statement_ids.filtered(lambda x: not x.pos_statement_id)
                # if statement_lines:
                #     statements = self.env['account.bank.statement']
                #     for stml in statement_lines:
                #         statements = (statements | stml.statement_id)
                #     statements.button_confirm_bank()

                moves = self.env['account.move']
                for st_line in statement_lines:
                    if st_line.statement_id.journal_id.type not in ['bank', 'cash']:
                        raise UserError(
                            _("The type of the journal for your payment method should be bank or cash "))
                    journal_entry_ids = self.env['account.move'].search([('statement_line_id', '=', st_line.id)])
                    if st_line.account_id and not journal_entry_ids.ids:
                        st_line.fast_counterpart_creation()
                    elif not journal_entry_ids.ids:
                        raise UserError(
                            _('All the account entries lines must be processed in order to close the statement.'))
                    moves = (moves | journal_entry_ids)
                if moves:
                    moves.post()

        return True

    @api.multi
    def action_paid(self):
        self.write({'state': 'paid'})
        if self[0] and self[0].pos_reference == 'REFUND':
            self[0].create_picking()
        # else:
        #     session = ConnectorSession(self.env.cr, self.env.uid, context=self.env.context)
        #     _create_picking_job.delay(session, 'pos.order', self.id)
        # _action_post_job.delay(session, 'pos.order', self.id)
        return True

    # def get_line_discount(self):
    #     ret = []
    #     pre_line = False
    #     for iindex in range(0, len(self.lines)):
    #         line = self.lines[iindex]
    #         product_name = ''
    #         if iindex > 0 and self.lines[iindex - 1].promotion_ids:
    #             pre_line = self.lines[iindex - 1]
    #
    #         if line.product_id.id == self.session_id.config_id.discount_promotion_product_id.id \
    #                 or line.product_id.id == self.session_id.config_id.discount_promotion_bundle_id.id \
    #                 or line.product_id.id == self.session_id.config_id.discount_product_id.id \
    #                 or line.product_id.id == self.session_id.config_id.tip_product_id.id:
    #
    #             if line.product_id.id == self.session_id.config_id.tip_product_id.id:
    #                 vals = {
    #                     'product': line.product_id.name,
    #                     'qty': line.qty,
    #                     'price_unit': line.price_unit,
    #                     'price_subtotal_incl': line.price_subtotal_incl,
    #                     'tax_code': ', '.join([tax.tax_code for tax in line.tax_ids])
    #                 }
    #                 ret.append(vals)
    #             else:
    #                 if pre_line:
    #                     for promotion in pre_line.promotion_ids:
    #                         if promotion.type_promotion == 2 and line.product_id.id == self.session_id.config_id.discount_promotion_product_id.id \
    #                                 or promotion.type_promotion == 1 and line.product_id.id == self.session_id.config_id.discount_product_id.id \
    #                                 or promotion.type_promotion == 3 and line.product_id.id == self.session_id.config_id.discount_promotion_bundle_id.id:
    #                             product_name = pre_line.promotion_ids[0].name
    #                             # taxes_code = []
    #                             # for tax in line.tax_ids:
    #                             #     taxes_code.append(tax.tax_code)
    #
    #                             vals = {
    #                                 'product': product_name,
    #                                 'qty': line.qty,
    #                                 'price_unit': line.price_unit,
    #                                 'price_subtotal_incl': line.price_subtotal_incl,
    #                                 'tax_code': ', '.join([tax.tax_code for tax in line.tax_ids])
    #                             }
    #                             ret.append(vals)
    #     return ret


    def get_line_discount(self):
        ret = []
        for iindex in range(0, len(self.lines)):
            line = self.lines[iindex]
            if line.product_id.id == self.session_id.config_id.discount_promotion_product_id.id \
                    or line.product_id.id == self.session_id.config_id.discount_promotion_bundle_id.id \
                    or line.product_id.id == self.session_id.config_id.discount_product_id.id \
                    or line.product_id.id == self.session_id.config_id.tip_product_id.id:
                if line.product_id.id == self.session_id.config_id.tip_product_id.id:
                    vals = {
                        'product': line.product_id.name,
                        'qty': line.qty,
                        'price_unit': round(line.price_unit, 2),
                        'price_subtotal_incl': line.price_subtotal_incl,
                        'tax_code': ', '.join([tax.tax_code for tax in line.tax_ids])
                    }
                    ret.append(vals)
                else:
                    vals = {
                        'product': line.promotion_ids[0].name,
                        'qty': line.qty,
                        'price_unit': round(line.price_unit, 2),
                        'price_subtotal_incl': line.price_subtotal_incl,
                        'tax_code': ', '.join([tax.tax_code for tax in line.tax_ids])
                    }
                    ret.append(vals)
        return ret

    def create_from_ui(self, cr, uid, orders, context=None):
        # Keep only new orders
        submitted_references = [o['data']['name'] for o in orders]
        existing_order_ids = self.search(cr, uid, [('pos_reference', 'in', submitted_references)], context=context)
        existing_orders = self.read(cr, uid, existing_order_ids, ['pos_reference'], context=context)
        existing_references = set([o['pos_reference'] for o in existing_orders])
        orders_to_save = [o for o in orders if o['data']['name'] not in existing_references]

        # Remove existing ref on POS
        # order_ids = []
        order_ids = [o['id'] for o in orders if o['data']['name'] in existing_references]
        for tmp_order in orders_to_save:
            to_invoice = tmp_order['to_invoice']
            order = tmp_order['data']

            if to_invoice:
                self._match_payment_to_invoice(cr, uid, order, context=context)

            order_id = self._process_order(cr, uid, order, context=context)
            # Return POS order's ids instead of back-end order's ids in order to remove them on POS later.
            # order_ids.append(order_id)
            order_ids.append(tmp_order['id'])
            try:
                self.signal_workflow(cr, uid, [order_id], 'paid')
            except psycopg2.OperationalError:
                # do not hide transactional errors, the order(s) won't be saved!
                raise
            except Exception as e:
                _logger.error('Could not fully process the POS Order: %s', tools.ustr(e))

            if to_invoice:
                self.action_invoice(cr, uid, [order_id], context)
                order_obj = self.browse(cr, uid, order_id, context)
                self.pool['account.invoice'].signal_workflow(cr, SUPERUSER_ID, [order_obj.invoice_id.id], 'invoice_open')

        return order_ids

    def br_get_rounding_payment(self):
        rounding_line = [statement for statement in self.statement_ids if statement.journal_id.is_rounding_method is True]
        round_val = 0.0
        if rounding_line:
            round_val = rounding_line[0].amount
        return round_val
        # value = self.amount_total
        # ret = 0
        # for line in self.lines:
        #     if line.product_id.id == self.env.user.company_id.rounding_product_id.id:
        #         ret = line.price_unit
        # return ret


class br_pos_order_line_master(models.Model):
    _name = 'br.pos.order.line.master'
    _description = "Lines Master of Point of Sale"

    @api.one
    @api.depends('order_id', 'product_id')
    def _compute_name(self):
        if self.product_id:
            index = 1
            for master in self.order_id.master_ids:
                if self == master:
                    self.name = str(index)
                    break
                else:
                    index += 1

    @api.one
    def _amount_line_all(self):
        cur = self.order_id.pricelist_id.currency_id
        taxes_ids = [tax for tax in self.tax_ids if tax.company_id.id == self.order_id.company_id.id]
        fiscal_position_id = self.order_id.fiscal_position_id
        if fiscal_position_id:
            taxes_ids = fiscal_position_id.map_tax(taxes_ids)
        price = self.price_unit
        self.price_subtotal = price * self.qty
        self.price_subtotal_incl = price * self.qty
        if taxes_ids:
            taxes = taxes_ids[0].compute_all(price, cur, self.qty, product=self.product_id,
                                             partner=self.order_id.partner_id or False)
            self.price_subtotal = taxes['total_excluded']
            self.price_subtotal_incl = taxes['total_included']

    company_id = fields.Many2one('res.company', string="Company", required=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char('Number', compute='_compute_name', store=True)
    product_id = fields.Many2one('product.product', string="Menu Name", domain=[('sale_ok', '=', True)],
                                 required=True, change_default=True)
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'))
    qty = fields.Float('Quantity', digits=dp.get_precision('Product Unit of Measure'), defaults=lambda *a: 1)
    price_subtotal = fields.Float(string='Subtotal w/o Tax', compute='_amount_line_all',
                                  digits=dp.get_precision('Account'))
    price_subtotal_incl = fields.Float(string='Subtotal', compute='_amount_line_all',
                                       digits=dp.get_precision('Account'))
    discount = fields.Float('Discount (%)', digits=dp.get_precision('Discount'), defaults=lambda *a: 0.0)
    discount_amount = fields.Float(string='Discount amount', digits=dp.get_precision('Product Price'))
    order_id = fields.Many2one('pos.order', string="Product Master", ondelete='cascade', required=True)
    tax_ids = fields.Many2many('account.tax', string='Taxes')

    user_promotion = fields.Many2one('res.users', string='Staff')
    non_sale = fields.Boolean(string='Non-sale', default=False)
    line_master_id = fields.Integer(string="Line Master Id")
    rate_promotion = fields.Float(string="Rate Promotion")
    order_lines = fields.One2many('pos.order.line', 'master_id', 'Order Lines')

    def get_taxes_code(self):
        taxes_code = []
        taxes_ids = [tax for tax in self.tax_ids if tax.company_id.id == self.order_id.company_id.id]
        fiscal_position_id = self.order_id.fiscal_position_id
        if fiscal_position_id:
            taxes_ids = fiscal_position_id.map_tax(taxes_ids)
        for tax in taxes_ids:
            taxes_code.append(tax.tax_code)
        return ', '.join(taxes_code)


class br_pos_order_line(models.Model):
    _inherit = 'pos.order.line'
    _order = 'master_id'

    @api.model
    def _order_line_fields(self, line):
        # FIXME: Why not call super ?
        # If order line's product is ice cream flavour then set price unit as price flavour
        if 'product_master_id' in line[2]:
            if line[2]['product_master_id']:
                if line[2]['price_unit'] >= 0:
                    line[2]['price_unit'] = line[2]['price_flavor']
                    if 'total_qty' in line[2]:
                        line[2]['qty'] = line[2]['total_qty']
                    product = self.env['product.product'].browse(line[2]['product_id'])
                    line[2]['standard_price'] = product.standard_price
                else:
                    return line
            else:
                return False
        # By default get tax from product
        if line and 'tax_ids' not in line[2]:
            product = self.env['product.product'].browse(line[2]['product_id'])
            line[2]['tax_ids'] = [(6, 0, [x.id for x in product.taxes_id])]
        return line

    # FIXME: This function should belong to model br.pos.order.line.master
    @api.model
    def _order_master_fields(self, line):
        if 'product_master_id' in line[2] and not line[2]['product_master_id'] and line[2]['price_unit'] >= 0:
            return line
        return False

    user_promotion = fields.Many2one('res.users', string='Staff', ondelete='restrict')
    # FIXME: move this field to pos.order (might affect sales report)
    non_sale = fields.Boolean(string='Non-sale', default=False)
    line_master_id = fields.Integer(string="Line Master Id")
    rate_promotion = fields.Float(string="Rate Promotion")
    is_bundle_item = fields.Boolean("Is Bundle Item", defaults=False)
    master_id = fields.Many2one('br.pos.order.line.master', string="Menu Name", change_default=True)
    discount_amount = fields.Float(string='Discount amount', digits=dp.get_precision('Product Price'))
    menu_name_id = fields.Many2one('product.product', related='master_id.product_id')
    standard_price = fields.Float('Product \'s Standard Price')
    group_name = fields.Char("Product Group Name")
    show_in_cart = fields.Boolean("Show in cart", default=True)
    price_unit = fields.Float(string='Unit Price', digits=dp.get_precision('Product Price'))


class br_pos_config(models.Model):
    _inherit = 'pos.config'

    fiscal_position_ids = fields.Many2one(comodel_name='account.fiscal.position', string='Fiscal Positions')
    default_payment_method = fields.Many2one(comodel_name='account.journal', string=_("Default Payment Method"))
    sequence_number = fields.Integer(string=_("Sequence Number"))
    code = fields.Char(string=_("Code"), required=True)
    is_trade_sales = fields.Boolean(string='Is Trade Sales?', default=False)
    pc_number = fields.Char(string='Dunkin PC Number')

    _defaults = {
        'sequence_number': 1
    }


class br_account_journal(models.Model):
    _inherit = 'account.journal'

    is_rounding_method = fields.Boolean(string=_("Rounding Payment Method"))
    edc_terminal = fields.Selection([
        ('maybank_sale', 'May Bank'),
        ('maybank_redeemPoint', 'May Bank TreatsPoints'),
        ('maybank_redeemValue', 'May Bank Value'),
        ('rhbbank_sale', 'RHB Bank'),
        ('cimb_sale', 'Credit/Debit Card - CIMB Terminal'),
        ('cimb_ewallet', 'Integrated E Wallet - CIMB Terminal'),
        ('manual_ewallet', 'Manual E Wallet'),
        ('cimb_bonusPoint', 'CIMB Bonus Points')
    ])
    payment_type = fields.Selection(selection=[('on_site', 'On Site'),
                                               ('off_site', 'Off Site'),
                                               ('redemption', 'Redemption')],
                                    string='Payment Type', default='on_site')
    is_non_clickable = fields.Boolean(string='Not Clickable in POS',
                                      default=False)
    is_required_thirdparty = fields.Boolean(string='Need 3rd Party ID',
                                            default=False)
    e_wallet_id = fields.Many2one('e.wallet.platform', string='E-Wallet')
    e_wallet_cimb_code = fields.Char(related='e_wallet_id.cimb_machine_code',
                                     string='CIMB Machine Code')
    background_colour = fields.Char(string='Background Colour',
                                    help="Choose your background color",
                                    default="#FFB6C1")
    font_colour = fields.Char(string='Font Colour',
                              help="Choose your font color",
                              default="#FFFFFF")

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self.env.context.get('journal_ids', False):
            journal_ids = self.env.context.get('journal_ids')
            args.append(['id', 'in', journal_ids[0][2]])
        return super(br_account_journal, self)._search(args, offset=offset, limit=limit, order=order, count=count,
                                                       access_rights_uid=access_rights_uid)

    @api.constrains('is_rounding_method')
    def _check_is_rounding_method(self):
        count = len(self.search([('company_id', '=', self.company_id.id), ('is_rounding_method', '=', True)]))
        if count > 1:
            raise ValidationError(_("There can be only one rounding payment method per company"))

    @api.onchange('edc_terminal')
    def _onchange_edc_terminal(self):
        if not self.edc_terminal == 'cimb_ewallet':
            self.e_wallet_id = False
