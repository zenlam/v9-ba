# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from collections import OrderedDict
from openerp.exceptions import UserError, ValidationError
from ast import literal_eval
from hashlib import sha1
from datetime import datetime
from openerp.addons.connector.session import (
    ConnectorSession
)
from openerp.addons.restful.models.rest_api_log import (
    _recall_api
)


class Promotion(models.Model):
    _inherit = "br.bundle.promotion"

    mobile_promotion = fields.Boolean(related='third_party_id.is_mobile_apps')
    free_deal = fields.Boolean(string='Free Coupon', default=False)
    flexible_end_date = fields.Boolean(string='Flexible End Date',
                                       default=False)
    validity_days = fields.Integer(string='Validity (in Days)')
    suspend_promotion = fields.Boolean(string='Suspend', default=False,
                                       readonly=1)
    promotion_description = fields.Text(
        string='Description', help="This description will be shown in the "
                                   "third party platform.")

    @api.model
    def deactivate_suspend_promotion(self):
        """ Deactivate the suspended promotion which has no redeemable coupon
        """
        suspended_promotions = self.search([('suspend_promotion', '=', True)])
        for promotion in suspended_promotions:
            if not any([voucher.status == 'available'
                        for voucher in promotion.voucher_ids]):
                promotion.active = False

    @api.onchange('mobile_promotion')
    def onchange_mobile_promotion(self):
        # set default value of code configuration when the promotion is a
        # mobile promotion
        if self.mobile_promotion:
            self.default_number_of_alphabet = 1
            self.default_number_of_digit = 3
            self.default_remarks = 'Mobile Apps'

    @api.onchange('flexible_end_date')
    def onchange_flexible_end_date(self):
        # when a mobile promotion's flexible end date is unchecked, then set
        # validity_days to 0
        if not self.flexible_end_date:
            self.validity_days = 0

    @api.constrains('third_party_id', 'free_deal', 'is_hq_voucher')
    def _check_free_redemption(self):
        if self.third_party_id and self.mobile_promotion:
            if self.free_deal and self.is_hq_voucher:
                raise ValidationError(_('A third party discount should not '
                                        'have Free Coupon and Is Redemption '
                                        'at the same time.'))
            if not self.free_deal and not self.is_hq_voucher:
                raise ValidationError(_('A third party discount should at '
                                        'least belongs to Is Redemption or '
                                        'Free Coupon".'))

    @api.constrains('third_party_id', 'flexible_end_date', 'end_date')
    def _check_flexible_date(self):
        if self.third_party_id and self.mobile_promotion:
            if self.flexible_end_date and self.end_date:
                raise ValidationError(_('End date field should be empty if '
                                        'this is a flexible end date '
                                        'discount.'))
            if not self.flexible_end_date and not self.end_date:
                raise ValidationError(_('A non-flexible end date discount '
                                        'should have an end date.'))

    @api.multi
    def sync_data(self):
        """
        Sync the promotion data to Mobile Apps
        """
        for rec in self:
            try:
                company = self.env.user.company_id
                success = False
                if rec.mobile_promotion:
                    api_log_obj = self.env['rest.api.log']
                    sync_log_obj = self.env['third.party.promotion.sync.log']
                    sync_status = 'unreachable'
                    # fields to sync back to Mobile Apps
                    tracking_fields = [
                        'code', 'name', 'promotion_description', 'start_date',
                        'end_date', 'free_deal', 'flexible_end_date',
                        'validity_days', 'suspend_promotion']
                    # message to be shown in sync log
                    field_msg = ''
                    # list of coupon which are going to be updated
                    coupons_list = []
                    # dictionary (key: Field String, value: Field Value)
                    tracking_value = OrderedDict()
                    tracking_chatter_value = OrderedDict()
                    for field in tracking_fields:
                        field_attribute = rec.fields_get(field)
                        string = field_attribute[field].get('string')
                        value = getattr(rec, field)
                        if field_attribute[field].get('type') == 'many2one':
                            value = value.name_get()[0][1]
                        elif field_attribute[field].get('type') == 'many2many':
                            value = ','.join([val.name_get()[0][1]
                                              for val in value])
                        elif field_attribute[field].get('type') == 'selection':
                            value = dict(
                                rec._fields[field].selection).get(value)
                        tracking_chatter_value[string] = value
                        tracking_value[field] = value

                    # populate the last sync info and store in the promotion
                    # model
                    last_sync_info = ','.join([str(field_value)
                                               for field_key, field_value
                                               in tracking_value.items()])

                    # if the current sync data is same as the last sync info,
                    # then skip the third party sync
                    if rec.last_sync_info == last_sync_info:
                        continue

                    # Mobile Apps API Calling
                    headers = {
                        'content-type': 'application/x-www-form-urlencoded',
                        'charset': 'utf-8',
                        'platform': 'odoo'
                    }
                    # Sign Algorithm
                    sign = sha1((tracking_value['code'] +
                                 tracking_value['name'] +
                                 rec.third_party_id.sign_keyword).
                                encode('utf-8')).hexdigest()
                    # data to be passed to API calls
                    data = {
                        'coupon_type_id': tracking_value['code'],
                        'coupon_type_name': tracking_value['name'],
                        'coupon_type_desc': tracking_value[
                            'promotion_description'],
                        'coupon_type_start_date': tracking_value['start_date'],
                        'coupon_type_end_date': tracking_value['end_date'],
                        'free_coupon': tracking_value['free_deal'],
                        'flexible_end_date': tracking_value['flexible_end_date'],
                        'validity': tracking_value['validity_days'],
                        'suspend': tracking_value['suspend_promotion'],
                        'sign': sign
                    }
                    # Third Party API Endpoint
                    url = '{api_url}{endpoint}'.format(
                        api_url=rec.third_party_id.api_url,
                        endpoint=rec.third_party_id.promotion_sync_endpoint
                    )
                    # call update API
                    if rec.sync_id:
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
                        # update the coupon code start date and end date
                        if api_call.request_status == '200':
                            response = literal_eval(api_call.request_response)
                            status_code = response.get('code')
                            if status_code == 1 and 'data' in response:
                                # if successfully update the coupon type info,
                                # then start to check for coupon code update
                                coupons = rec.voucher_ids.filtered(
                                    lambda x: x.status == 'available')
                                # if there are some voucher related to this
                                # promotion, update the voucher start end date
                                # and get the value dictionary.
                                if coupons:
                                    coupons_list = coupons.update_coupon_sync()
                    # call create API
                    else:
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
                            response = literal_eval(api_call.request_response)
                            status_code = response.get('code')
                            if status_code == 1 and 'data' in response:
                                rec.sync_id = response['data']

                    message = "Promotion Data Sync Failed: <b>%s</b>" % \
                              rec.third_party_id.name
                    if api_call.request_status == '200':
                        success = True
                        response = literal_eval(api_call.request_response)
                        status_code = response.get('code')
                        sync_status = 'fail'
                        if status_code == 1:
                            # create sync log message
                            for field_string, field_value \
                                    in tracking_chatter_value.items():
                                field_msg += field_string + ': ' + \
                                             str(field_value) + '<br/>'
                            message = \
                                "Promotion Data Sync: <b>%s</b><br/><br/>%s" \
                                "<br/>Updated Vouchers:<br/>%s" %\
                                (rec.third_party_id.name, field_msg,
                                 coupons_list)
                            sync_status = 'success'
                            rec.last_sync_info = last_sync_info
                    if not success:
                        session = ConnectorSession(self.env.cr,
                                                   self.env.user.id,
                                                   context=self.env.context)
                        _recall_api.delay(
                            session,
                            'br.bundle.promotion',
                            rec.id,
                            'sync_data',
                            eta=60 * company.repeat_attempts_count)
                    # create sync log
                    sync_log_obj.create({
                        'sync_datetime': datetime.now(),
                        'sync_info': message,
                        'sync_status': sync_status,
                        'rec_id': rec.code,
                        'rec_name': rec.real_name,
                        'third_party_id': self.env.ref(
                            'baskin_integration_mobile.third_party_fugumobile').id
                    })
                self.env.cr.commit()
            except Exception:
                raise UserError(_('Something is not right with promotion %s. '
                                  'Kindly check the promotion configuration.')
                                % rec.real_name)
        return super(Promotion, self).sync_data()

    @api.multi
    def suspend(self):
        """
        Suspend the promotion from Mobile Apps
        """
        for rec in self:
            if rec.mobile_promotion:
                api_log_obj = self.env['rest.api.log']
                # fields to sync back to Mobile Apps
                tracking_fields = [
                    'code', 'name', 'promotion_description', 'start_date',
                    'end_date', 'free_deal', 'flexible_end_date',
                    'validity_days', 'suspend_promotion']
                # dictionary (key: Field String, value: Field Value)
                tracking_value = OrderedDict()
                for field in tracking_fields:
                    field_attribute = rec.fields_get(field)
                    value = getattr(rec, field)
                    if field_attribute[field].get('type') == 'many2one':
                        value = value.name_get()[0][1]
                    elif field_attribute[field].get('type') == 'selection':
                        value = dict(
                            rec._fields[field].selection).get(value)
                    tracking_value[field] = value
                # Mobile Apps API Calling
                headers = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'charset': 'utf-8',
                    'platform': 'odoo'
                }
                # Sign Algorithm
                sign = sha1((tracking_value['code'] +
                             tracking_value['name'] +
                             rec.third_party_id.sign_keyword).
                            encode('utf-8')).hexdigest()
                # data to be passed to API calls
                data = {
                    'coupon_type_id': tracking_value['code'],
                    'coupon_type_name': tracking_value['name'],
                    'coupon_type_desc': tracking_value[
                        'promotion_description'],
                    'coupon_type_start_date': tracking_value['start_date'],
                    'coupon_type_end_date': tracking_value['end_date'],
                    'free_coupon': tracking_value['free_deal'],
                    'flexible_end_date': tracking_value['flexible_end_date'],
                    'validity': tracking_value['validity_days'],
                    'suspend': True,
                    'sign': sign
                }
                # Third Party API Endpoint
                url = '{api_url}{endpoint}'.format(
                    api_url=rec.third_party_id.api_url,
                    endpoint=rec.third_party_id.promotion_sync_endpoint
                )
                # call update API
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
                message = "Promotion Suspension Failed: <b>%s</b>" % \
                          rec.third_party_id.name
                if api_call.request_status == '200':
                    response = literal_eval(api_call.request_response)
                    status_code = response.get('code')
                    if status_code == 1:
                        rec.suspend_promotion = True
                        message = "Promotion Being Suspended from <b>%s</b> " \
                                  "by %s." % (rec.third_party_id.name,
                                              self.env.user.name)
                rec.message_post(body=message)
            return super(Promotion, self).suspend()
