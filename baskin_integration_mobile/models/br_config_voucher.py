# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError
from ast import literal_eval
from hashlib import sha1
import json
from datetime import datetime, timedelta
from openerp.addons.connector.session import (
    ConnectorSession
)
from openerp.addons.restful.models.rest_api_log import (
    _recall_api
)

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
APPROVAL_DATETIME = "%Y%m%d-%H%M%S"
DATE_FORMAT = "%Y-%m-%d"


class Voucher(models.Model):
    _inherit = "br.config.voucher"

    third_party_id = fields.Many2one(
        'third.party', string='Third Party',
        related='promotion_id.third_party_id')
    sync_id = fields.Char(
        string='Sync ID',
        help='The record ID of third party database. The value is returned '
             'from the third party after Odoo syncing the data.',
        related='promotion_id.sync_id')
    free_deal = fields.Boolean(string='Free Coupon',
                               related='promotion_id.free_deal')
    flexible_end_date = fields.Boolean(string='Flexible End Date',
                                       related='promotion_id.flexible_end_date')
    validity_days = fields.Integer(string='Validity (in Days)',
                                   related='promotion_id.validity_days')
    suspend_promotion = fields.Boolean(string='Suspend',
                                       related='promotion_id.suspend_promotion')

    @api.model
    def create(self, vals):
        """ do not allow to create coupon if the parent promotion is already
        suspended """
        promotion = self.env['br.bundle.promotion'].browse(
            vals.get('promotion_id'))
        if promotion.suspend_promotion:
            raise UserError(_("Discount is being suspended."))
        return super(Voucher, self).create(vals)

    @api.model
    def get_promotion_from_voucher(self, voucher_validation_code, outlet):
        """ Do the validation of voucher code then check for membership """
        res = super(Voucher, self).get_promotion_from_voucher(
            voucher_validation_code, outlet)
        voucher_info = \
            self.check_promotion_member(voucher_validation_code) or \
            [False, False, False, False, False]
        member_code = voucher_info[0]
        member_name = voucher_info[2]
        shared_voucher = voucher_info[4]
        res.extend([member_code, member_name, shared_voucher])
        return res

    @api.model
    def check_promotion_member(self, voucher_validation_code):
        """ Handle the logic of Mobile Apps Member Voucher Code """
        voucher = self.search([
            ('voucher_validation_code', '=', voucher_validation_code)],
            limit=1)
        # check if the voucher is belong to Mobile Apps Voucher
        if voucher and \
                voucher.promotion_id and \
                voucher.promotion_id.third_party_id and \
                voucher.promotion_id.third_party_id.is_mobile_apps:
            if voucher.member_id:
                return [voucher.member_id.code, voucher.member_id.id,
                        voucher.member_id.name,
                        voucher.promotion_id.third_party_id.id,
                        voucher.shared_voucher]
            else:
                # need to call their API to query coupon's member
                third_party = voucher.promotion_id.third_party_id
                coupon = third_party.query_coupon(voucher_validation_code)
                if coupon:
                    return [coupon.member_id.code, coupon.member_id.id,
                            coupon.member_id.name,
                            voucher.promotion_id.third_party_id.id,
                            voucher.shared_voucher]
                return [False, False, False,
                        voucher.promotion_id.third_party_id.id,
                        voucher.shared_voucher]
        return super(Voucher, self).check_promotion_member(
            voucher_validation_code)

    @api.model
    def get_membership_id(self):
        query = """
                    SELECT bcv.id FROM br_config_voucher bcv
                    JOIN br_bundle_promotion bbp ON bcv.promotion_id = bbp.id
                    JOIN third_party tp ON bbp.third_party_id = tp.id
                    WHERE tp.is_mobile_apps = TRUE and bcv.member_id is NULL
                """
        self.env.cr.execute(query)
        vouchers = [x[0] for x in self.env.cr.fetchall()]
        vouchers = self.search([('id', 'in', vouchers)])
        if vouchers:
            for voucher in vouchers:
                third_party = voucher.promotion_id.third_party_id
                coupon = third_party.query_coupon(voucher.voucher_validation_code)
                if coupon:
                    voucher.member_id = coupon.member_id.id
        return super(Voucher, self).get_membership_id()

    @api.multi
    def update_coupon_sync(self):
        """ Handle the logic of updating the coupon code of Mobile Apps.
        Inherit this function """
        # get the coupons
        coupons = self.browse(self.ids)
        if not coupons:
            return False
        # get the general information of the parent promotion and third party
        third_party_id = coupons[0].third_party_id
        promotion_id = coupons[0].promotion_id
        company = self.env.user.company_id
        success = False
        # rest api log object
        api_log_obj = self.env['rest.api.log']
        if third_party_id.is_mobile_apps:
            # initialize the coupon list to update
            coupon_data = []
            for coupon in coupons:
                # compare the request date and promotion start date
                # only amend the coupon start date when the promotion start
                # date is later than the request date. Otherwise, the coupon
                # start date will be the request date
                request_date = \
                    (datetime.strptime(coupon.create_date, DATETIME_FORMAT) +
                     timedelta(hours=8)).date()
                promotion_start_date = datetime.strptime(
                    promotion_id.start_date, DATE_FORMAT).date()
                if promotion_start_date > request_date:
                    start_date = promotion_start_date
                else:
                    start_date = request_date
                # if the promotion is flexible end date promotion, then add
                # the validity to the start date to get the end date. Otherwise
                # just take the promotion end date
                if promotion_id.flexible_end_date:
                    validity = promotion_id.validity_days
                    end_date = (start_date + timedelta(days=validity))
                else:
                    end_date = promotion_id.end_date
                # do not need to include the unchanged coupon to the list
                if coupon.start_date == str(start_date) and \
                        coupon.end_date == str(end_date):
                    continue

                coupon_data.append({
                    'coupon_code': str(coupon.voucher_validation_code),
                    'start_date': str(start_date),
                    'end_date': str(end_date)
                })
            if not coupon_data:
                return False
            # Mobile Apps API Calling
            headers = {
                'content-type': 'application/x-www-form-urlencoded',
                'charset': 'utf-8',
                'platform': 'odoo'
            }
            # Sign Algorithm
            sign = sha1((''.join([coupon['coupon_code']
                                  for coupon in coupon_data[:10]]) +
                         third_party_id.sign_keyword).
                        encode('utf-8')).hexdigest()
            # data to be passed to API calls
            data = {
                'list': json.dumps(coupon_data),
                'sign': sign
            }
            # Third Party API Endpoint
            url = '{api_url}{endpoint}'.format(
                api_url=third_party_id.api_url,
                endpoint=third_party_id.coupon_code_update_endpoint
            )
            # create API Log
            api_call = api_log_obj.create({
                'request_method': 'PUT',
                'request_url': url,
                'request_headers': headers,
                'request_uid': self.env.user.id,
                'request_time': datetime.now(),
                'request_arguments': data,
                'request_direction': 'outgoing'
            })
            # run the API Call
            api_call.run()
            if api_call.request_status == '200':
                success = True
            # if the coupon code is successfully updated in third party,
            # update the coupon code in Odoo
            if success:
                for coupon_dict in coupon_data:
                    coupon = self.search([
                        ('voucher_validation_code', '=',
                         coupon_dict['coupon_code'])])
                    coupon.write({
                        'start_date': coupon_dict['start_date'],
                        'end_date': coupon_dict['end_date']
                    })
                return coupon_data
            else:
                session = ConnectorSession(self.env.cr,
                                           self.env.user.id,
                                           context=self.env.context)
                _recall_api.delay(session, 'br.config.voucher', coupons.ids,
                                  'update_coupon_sync',
                                  eta=60 * company.repeat_attempts_count)
                return False
        return super(Voucher, self).update_coupon_sync()
