# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
import json
from hashlib import sha1
from datetime import datetime
from ast import literal_eval
from openerp.addons.connector.session import (
    ConnectorSession
)
from openerp.addons.restful.models.rest_api_log import (
    _recall_api
)


class POSOrder(models.Model):
    _inherit = "pos.order"

    @api.multi
    def sync_transaction(self):
        """ Sync the POS Order transaction detail to Mobile Apps """
        for rec in self:
            company = self.env.user.company_id
            success = False
            if rec.third_party.is_mobile_apps:
                api_log_obj = self.env['rest.api.log']
                # fields to sync back to Mobile Apps
                member_code = str(rec.member_code)
                store_id = str(rec.outlet_id.id)
                # handle qr_code logic, only send the coupon code related to
                # this third party
                qr_codes = []
                if rec.vouchers:
                    voucher_codes = rec.vouchers.split(',')
                    for code in voucher_codes:
                        code_id = self.env['br.config.voucher'].search([
                            ('voucher_validation_code', '=', code.strip())])
                        # append to the list if the code is belong to this 
                        # third party
                        if code_id.third_party_id.id == rec.third_party.id:
                            qr_codes.append(code.strip())
                qr_code = ','.join(qr_codes)
                pos_id = '1'
                payment_channel = ','.join(
                    set([statement.journal_id.name
                         for statement in rec.statement_ids
                         if not statement.journal_id.is_rounding_method]))
                order_id = str(rec.name)
                detail_item = [{'sku': str(menu.product_id.id),
                                'quantity': str(menu.qty),
                                'price': str(menu.price_unit),
                                'name': str(menu.product_id.name)}
                               for menu in rec.master_ids]
                order_datetime = rec.date_order
                # difference between amount and point amount
                # amount: total amount of the order including the onsite,
                # offsite and redemption
                # point amount: total amount of the order (onsite only)
                # loyalty points will be given based on the point amount
                # instead of the amount (full amount)
                amount = str(rec.amount_total)
                point_amount = str(sum([statement.amount
                                        for statement in rec.statement_ids
                                        if statement.journal_id and
                                        statement.journal_id.payment_type
                                        == 'on_site']))
                # Mobile Apps API Calling
                headers = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'charset': 'utf-8',
                    'platform': 'odoo'
                }
                # Sign Algorithm
                sign = sha1((order_id + order_datetime +
                             rec.third_party.sign_keyword).
                            encode('utf-8')).hexdigest()
                # data to be passed to API calls
                data = {
                    'member_code': member_code,
                    'storeid': store_id,
                    'qrcode': qr_code,
                    'posid': pos_id,
                    'paymentchannel': payment_channel,
                    'orderid': order_id,
                    'detailitem': json.dumps(detail_item),
                    'datetime': order_datetime,
                    'amount': amount,
                    'point_amount': point_amount,
                    'sign': sign
                }
                # Third Party API Endpoint
                url = '{api_url}{endpoint}'.format(
                    api_url=rec.third_party.api_url,
                    endpoint=rec.third_party.order_sync_endpoint
                )
                # call the transaction API
                # create API Log
                api_call = api_log_obj.create({
                    'request_method': 'POST',
                    'request_url': url,
                    'request_headers': headers,
                    'request_uid': self.env.user.id,
                    'request_time': datetime.now(),
                    'request_arguments': data,
                    'request_direction': 'outgoing'
                })
                # run the API Call
                api_call.run()
                # update the sync_id from the response
                if api_call.request_status == '200':
                    success = True
                    response = literal_eval(api_call.request_response)
                    status_code = response.get('code')
                    if status_code == 1 and 'orderid' in response:
                        rec.sync_id = response['orderid']
                if not success:
                    session = ConnectorSession(self.env.cr,
                                               self.env.user.id,
                                               context=self.env.context)
                    _recall_api.delay(session, 'pos.order', rec.id,
                                      'sync_transaction',
                                      eta=60 * company.repeat_attempts_count)
        return super(POSOrder, self).sync_transaction()

    @api.multi
    def sync_cancel_transaction(self):
        """ Sync the cancelled POS Order transaction detail to Mobile Apps """
        for rec in self:
            company = self.env.user.company_id
            success = False
            if rec.third_party.is_mobile_apps:
                api_log_obj = self.env['rest.api.log']
                # fields will be synced to Mobile Apps
                order_id = str(rec.name)
                # Mobile Apps API Calling
                headers = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'charset': 'utf-8',
                    'platform': 'odoo'
                }
                # Sign Algorithm
                sign = sha1((order_id + rec.third_party.sign_keyword).
                            encode('utf-8')).hexdigest()
                # data to be passed to API calls
                data = {
                    'orderid': order_id,
                    'sign': sign
                }
                # Third Party API Endpoint
                url = '{api_url}{endpoint}'.format(
                    api_url=rec.third_party.api_url,
                    endpoint=rec.third_party.order_cancel_sync_endpoint
                )
                # call the cancel transaction API
                # create API Log
                api_call = api_log_obj.create({
                    'request_method': 'POST',
                    'request_url': url,
                    'request_headers': headers,
                    'request_uid': self.env.user.id,
                    'request_time': datetime.now(),
                    'request_arguments': data,
                    'request_direction': 'outgoing'
                })
                # run the API Call
                api_call.run()
                # update the refund order's sync_id from the response
                if api_call.request_status == '200':
                    success = True
                    response = literal_eval(api_call.request_response)
                    status_code = response.get('code')
                    if status_code == 1 and 'orderid' in response:
                        rec.refund_order_id.sync_id = response['orderid'] + \
                                                      '-REFUND'
                if not success:
                    session = ConnectorSession(self.env.cr,
                                               self.env.user.id,
                                               context=self.env.context)
                    _recall_api.delay(session, 'pos.order', rec.id,
                                      'sync_cancel_transaction',
                                      eta=60 * company.repeat_attempts_count)
        return super(POSOrder, self).sync_cancel_transaction()

    @api.model
    def get_pos_order_membership_id(self):
        # Voucher Purchase
        member_query = """
                           SELECT po.id FROM pos_order po
                           JOIN third_party tp ON po.third_party = tp.id
                           WHERE tp.is_mobile_apps = True
                           AND po.member_code is NULL
                           AND po.member_id is NULL
                           AND po.vouchers != ''
                           """
        self.env.cr.execute(member_query)
        pos_orders = [x[0] for x in self.env.cr.fetchall()]
        pos_orders = self.search([('id', 'in', pos_orders)])
        for order in pos_orders:
            # vouchers = "AB1, AB2, AB3"
            vouchers = order.vouchers.split(',')
            # vouchers = ["AB1"," AB2"," AB3"]
            vouchers = [voucher.strip() for voucher in vouchers]
            # vouchers = ["AB1","AB2","AB3"] remove space
            coupons = self.env['br.config.voucher'].search(
                [('voucher_validation_code', 'in', vouchers)])
            # In a single transaction, can only apply coupons from a same
            # member unless the coupon is a shared coupon
            coupons = coupons.filtered(
                lambda x: x.third_party_id and x.third_party_id.is_mobile_apps
                          and not x.shared_voucher)
            if coupons:
                coupon = coupons[0]
                member_data = self.env[
                    'br.config.voucher'].check_promotion_member(
                    coupon.voucher_validation_code)
                order.member_code = member_data[0]
                order.member_id = member_data[1]
            else:
                order.member_code = 'It is a shared mobile app coupon / ' \
                                    'Not mobile app coupon'

        # Member Purchase
        voucher_query = """
                           SELECT po.id FROM pos_order po
                           JOIN third_party tp on po.third_party = tp.id
                           WHERE po.member_code is not NULL
                           AND po.member_code not like '%: Member Not Found'
                           AND po.member_code not like '%shared mobile app%'
                           AND po.member_id is NULL
                           AND tp.is_mobile_apps = True
                           """
        self.env.cr.execute(voucher_query)
        pos_orders = [x[0] for x in self.env.cr.fetchall()]
        pos_orders = self.search([('id', 'in', pos_orders)])
        for order in pos_orders:
            member_code = order.member_code
            third_party_id = order.third_party.id
            try:
                member_data = self.env['third.party.member'].get_member_data(
                    member_code, third_party_id)
                order.member_id = member_data['id']
            except Exception as e:
                if e[0] == u'404':
                    continue
                elif e[0] == u'Member Not Found!':
                    order.member_code += ': Member Not Found'
        return super(POSOrder, self).get_pos_order_membership_id()
