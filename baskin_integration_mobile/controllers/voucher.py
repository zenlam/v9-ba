# -*- coding: utf-8 -*-

from openerp import http
from openerp.addons.restful.common import (
    extract_arguments,
    invalid_response,
    valid_response,
)
from datetime import datetime, timedelta
from openerp.http import request
from openerp.addons.restful.controllers.main import validate_token
from openerp.addons.restful.controllers.main import generate_api_log
from openerp.addons.restful.controllers.main import APIController
import ast

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
APPROVAL_DATETIME = "%Y%m%d-%H%M%S"
DATE_FORMAT = "%Y-%m-%d"


class VoucherApiController(APIController):

    @generate_api_log
    @validate_token
    @http.route("/api/fugu/coupon", type="http", auth="none", methods=["POST"],
                csrf=False)
    def create_coupon(self, **payload):
        """ Create coupon based on the payload.
        Payload Content:
        1. Coupon Type ID (Discount ID)
        2. Quantity
        3. Batch Unique Identifier
        :return: Coupons Details
        """
        coupon_type_id = payload.get('coupon_type_id')
        quantity = payload.get('quantity')
        batch_no = payload.get('batch_no')

        promotion = request.env['br.bundle.promotion'].sudo().search([
            ('code', '=', coupon_type_id)], limit=1)

        # return invalid response if promotion not found in the system
        if not promotion:
            return invalid_response(
                "Invalid Coupon Type",
                "This coupon type is not found in the system.",
                400
            )

        # return invalid response if batch number is not provided
        if not batch_no:
            return invalid_response(
                "No Batch Number",
                "Kindly provide a batch number for the coupon creation.",
                400
            )

        # return invalid response if quantity is not an integer
        if quantity:
            try:
                quantity = int(quantity)
            except Exception as e:
                return invalid_response(
                    "Invalid Quantity",
                    "Quantity error: %s." % e
                )

        # return invalid response if quantity is not provided or less than 0
        if not quantity or quantity < 0:
            return invalid_response(
                "Invalid Quantity",
                "Quantity should be more than 0.",
                400
            )

        # check the existence of the batch number. Sometimes, API call might
        # fail in the middle and Odoo has already created the coupons.
        # In this case, Odoo should return the previously created coupons
        # instead of creating new coupons.
        check_batch_query = """
            SELECT EXISTS(
             SELECT 1 from br_config_voucher
             WHERE promotion_id = %s
             AND batch_number = '%s')
            """ % (promotion.id, batch_no)
        request.cr.execute(check_batch_query)
        result = request.cr.fetchall()[0]

        # if True, return the previously created voucher_ids
        if result[0]:
            voucher_ids = request.env['br.config.voucher'].sudo().search([
                ('promotion_id', '=', promotion.id),
                ('batch_number', '=', batch_no)]).ids
        # if False, create new coupons and return the voucher_ids
        else:
            end_date = promotion.end_date
            start_date = \
                datetime.strptime(promotion.start_date, DATE_FORMAT).date()
            request_date = (datetime.now() + timedelta(hours=8)).date()
            # return invalid response if the coupon type has ended
            if end_date and \
                datetime.strptime(end_date, DATE_FORMAT).date() < request_date:
                return invalid_response(
                    "Error in Creating Coupon",
                    "Discount has ended at %s" % end_date,
                    405
                )

            # if the request date is later than the promotion start date, then
            # the coupon start date will be the request date.
            if start_date < request_date:
                start_date = request_date

            # if the promotion is using flexible end date, then add the
            # validity days to start date of coupon and use it as end date of
            # the coupon
            if promotion.flexible_end_date:
                end_date = start_date + timedelta(days=promotion.validity_days)

            vals = {
                'promotion_id': promotion.id,
                'qty': quantity,
                'start_date': start_date,
                'end_date': end_date,
                'number_of_digit': promotion.default_number_of_digit,
                'number_of_alphabet': promotion.default_number_of_alphabet,
                'use_validation_code': True,
                'approval_no': datetime.strftime(datetime.now() +
                                                 timedelta(hours=8),
                                                 APPROVAL_DATETIME),
                'remarks': promotion.default_remarks,
                'batch_number': batch_no
            }
            # create a wizard record in order to call the voucher gen function
            try:
                voucher_gen = \
                    request.env['br.promotion.voucher.gen'].sudo().create(vals)
                voucher_ids = voucher_gen.gen_base()
            except Exception as e:
                return invalid_response(
                    "Error in Creating Coupon",
                    str(e),
                    405
                )

        # create a list of voucher data as response.
        # Response includes voucher validation code, start date, end date, and
        # coupon type
        data = []
        voucher_ids = ', '.join([str(voucher) for voucher in voucher_ids])
        vouchers_query = """
        SELECT voucher_validation_code, start_date, end_date
        FROM br_config_voucher
        WHERE id in (%s)
        """ % voucher_ids
        request.cr.execute(vouchers_query)
        vouchers = request.cr.dictfetchall()

        for voucher in vouchers:
            data.append({
                'code': voucher['voucher_validation_code'],
                'start_date': voucher['start_date'],
                'end_date': voucher['end_date'],
                'coupon_type_id': coupon_type_id,
            })
        return valid_response(data)

    @generate_api_log
    @validate_token
    @http.route("/api/fugu/coupon", type="http", auth="none", methods=["PUT"],
                csrf=False)
    def edit_coupon(self, **payload):
        """ Edit coupon based on the payload.
        Payload Content:
        1. Coupon Code
        2. Member Code
        :return: Status Code
        """
        # get the coupon data from the payload
        data = payload.get('data')
        data = ast.literal_eval(data)

        for coupon in data:
            coupon_code = coupon['coupon_code']
            member_code = coupon['member_code']

            coupon_id = request.env['br.config.voucher'].sudo().search(
                [('voucher_validation_code', '=', coupon_code)], limit=1
            )
            member_id = request.env['third.party.member'].sudo().search(
                [('code', '=', member_code)], limit=1
            )

            # return invalid response if coupon code is not found in the system
            if not coupon_code or not coupon_id:
                return invalid_response(
                    "Invalid Coupon Code",
                    "This coupon code is not found in the system.",
                    400
                )

            # return invalid response if member id is not found in the system
            if not member_code or not member_id:
                return invalid_response(
                    "Invalid Member Code",
                    "This Member Code is not found in the system.",
                    400
                )

            # return invalid response if share value is not provided
            if 'share' not in coupon:
                return invalid_response(
                    "Share Attribute Error",
                    "Share value is not provided.",
                    400
                )

            # update the record
            try:
                coupon_id.sudo().write({
                    'member_id': member_id.id,
                    'shared_voucher':
                        True if coupon['share'] == 'True' else False
                })
            except Exception as e:
                return invalid_response(
                    "Error in Updating Coupon",
                    str(e),
                    405
                )
        response = {
            'result': 'Successfully updating %s records' % len(data)
        }
        return valid_response(response)
