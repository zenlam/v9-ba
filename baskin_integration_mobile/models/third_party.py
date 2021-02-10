# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from collections import OrderedDict
from ast import literal_eval
from hashlib import sha1
from datetime import datetime
from openerp.exceptions import UserError, ValidationError
from openerp.addons.connector.session import (
    ConnectorSession
)
from openerp.addons.restful.models.rest_api_log import (
    _recall_api
)


class ThirdParty(models.Model):
    _inherit = "third.party"

    is_mobile_apps = fields.Boolean(string='Is Mobile Apps', default=False)
    sign_keyword = fields.Char(string='Sign', default=False)

    @api.multi
    def query_member(self, member_code):
        """ Query the member information based on the member code from Mobile
        Apps
        """
        for rec in self:
            if rec.is_mobile_apps:
                api_log_obj = self.env['rest.api.log']
                # Mobile Apps API Calling
                headers = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'charset': 'utf-8',
                    'platform': 'odoo'
                }
                # Sign Algorithm
                sign = sha1((member_code + rec.sign_keyword)
                            .encode('utf-8')).hexdigest()

                # data to be passed to API calls
                if 'phone' in self.env.context and \
                        self.env.context.get('phone'):
                    data = {
                        'member_code': '',
                        'mobile': member_code,
                        'sign': sign
                    }
                else:
                    data = {
                        'member_code': member_code,
                        'mobile': '',
                        'sign': sign
                    }
                # Third Party API Endpoint
                # Hard code the endpoint due to this is only applicable to
                # Mobile Apps
                url = '{api_url}{endpoint}'.format(
                    api_url=rec.api_url,
                    endpoint='/pos/querymember'
                )
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
                self.env.cr.commit()
                # check the response
                if api_call.request_status == '200':
                    response = literal_eval(api_call.request_response)
                    status_code = response.get('code')
                    # if the member is found then create member and return
                    # member info
                    if status_code == 1 and 'member_code' in response:
                        member_exist = self.env['third.party.member'].search(
                           [('code', '=', response['member_code'])], limit=1)
                        if member_exist:
                            return member_exist
                        else:
                            # create the member in the member table
                            member = self.env['third.party.member'].create({
                                'name': response['name'],
                                'code': response['member_code'],
                                'member_level': response['member_level'],
                                'third_party_id': rec.id
                            })
                            return member
                    else:
                        raise ValidationError(_('Member Not Found!'))
                raise ValidationError(_('404'))
            return super(ThirdParty, self).query_member(member_code)

    @api.multi
    def query_coupon(self, coupon_code):
        """ Query the coupon's member information based on the coupon code
        from Mobile Apps
        """
        for rec in self:
            if rec.is_mobile_apps:
                api_log_obj = self.env['rest.api.log']
                # Mobile Apps API Calling
                headers = {
                    'content-type': 'application/x-www-form-urlencoded',
                    'charset': 'utf-8',
                    'platform': 'odoo'
                }
                # Sign Algorithm
                sign = sha1((coupon_code + rec.sign_keyword)
                            .encode('utf-8')).hexdigest()
                # data to be passed to API calls
                data = {
                    'coupon_code': coupon_code,
                    'sign': sign
                }
                # Third Party API Endpoint
                # Hard code the endpoint due to this is only applicable to
                # Mobile Apps
                url = '{api_url}{endpoint}'.format(
                    api_url=rec.api_url,
                    endpoint='/pos/querycoupon'
                )
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
                self.env.cr.commit()
                # check the response
                if api_call.request_status == '200':
                    response = literal_eval(api_call.request_response)
                    status_code = response.get('code')
                    # if the member is found then write the coupon and return
                    # member id
                    if status_code == 1 and 'member_code' in response:
                        # write the member in the voucher table
                        coupon = self.env['br.config.voucher'].search([
                            ('voucher_validation_code', '=', coupon_code)],
                            limit=1)
                        # check the member's existence
                        member_code = response['member_code']
                        member = self.env['third.party.member'].search([
                            ('code', '=', member_code),
                            ('third_party_id', '=', rec.id)], limit=1)
                        if not member:
                            member = rec.query_member(member_code)
                        coupon.write({
                            'member_id': member.id
                        })
                        return coupon
                return False
            return super(ThirdParty, self).query_coupon(coupon_code)


class ThirdPartyOutletSync(models.Model):
    _inherit = "third.party.outlet.sync"

    @api.multi
    def sync_data(self):
        """
        Sync the outlet data to Mobile Apps
        """
        for rec in self:
            try:
                company = self.env.user.company_id
                success = False
                if rec.third_party_id.is_mobile_apps:
                    api_log_obj = self.env['rest.api.log']
                    sync_log_obj = self.env['third.party.outlet.sync.log']
                    sync_status = 'unreachable'
                    # fields to sync back to Mobile Apps
                    tracking_fields = [
                        'name', 'outlet_phone', 'outlet_street1',
                        'outlet_street2', 'state_id', 'outlet_city',
                        'outlet_country', 'outlet_coord', 'outlet_zip',
                        'outlet_weekday_opening', 'outlet_weekend_opening',
                        'outlet_holiday_opening', 'mobile_status',
                        'outlet_type', 'facility_ids', 'visible_in_apps']
                    # message to be shown in sync log
                    field_msg = ''
                    # dictionary (key: Field String, value: Field Value)
                    tracking_value = OrderedDict()
                    tracking_chatter_value = OrderedDict()
                    for field in tracking_fields:
                        field_attribute = rec.outlet_id.fields_get(field)
                        string = field_attribute[field].get('string')
                        value = getattr(rec.outlet_id, field)
                        if field_attribute[field].get('type') == 'many2one':
                            value = value.name_get()[0][1]
                        elif field_attribute[field].get('type') == 'many2many':
                            value = ','.join([val.name_get()[0][1]
                                              for val in value])
                        elif field_attribute[field].get('type') == 'selection':
                            value = dict(
                                rec.outlet_id._fields[field].selection).get(
                                value)
                        tracking_chatter_value[string] = value
                        tracking_value[field] = value

                    # populate the last sync info and store in the outlet sync
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
                    sign = sha1((str(rec.outlet_id.id) +
                                 tracking_value['name'] +
                                 rec.third_party_id.sign_keyword).
                                encode('utf-8')).hexdigest()
                    # data to be passed to API calls
                    store_address = (tracking_value.get('outlet_street1')
                                     if tracking_value.get('outlet_street1')
                                     else '') + \
                                    (tracking_value.get('outlet_street2')
                                     if tracking_value.get('outlet_street2')
                                     else '')
                    data = {
                        'store_id': rec.outlet_id.id,
                        'store_name': tracking_value['name'],
                        'store_mobile': tracking_value['outlet_phone'],
                        'store_address': store_address,
                        'store_city': tracking_value['state_id'],
                        'store_state': tracking_value['outlet_city'],
                        'store_country': tracking_value['outlet_country'],
                        'store_coordinate': tracking_value['outlet_coord'],
                        'store_zip': tracking_value['outlet_zip'],
                        'weekday_opening':
                            tracking_value['outlet_weekday_opening'],
                        'weekend_opening':
                            tracking_value['outlet_weekend_opening'],
                        'holiday_opening':
                            tracking_value['outlet_holiday_opening'],
                        'store_status': tracking_value['mobile_status'],
                        'store_type': tracking_value['outlet_type'],
                        'store_facilities': tracking_value['facility_ids'],
                        'visible': tracking_value['visible_in_apps'],
                        'sign': sign
                    }
                    # Third Party API Endpoint
                    url = '{api_url}{endpoint}'.format(
                        api_url=rec.third_party_id.api_url,
                        endpoint=rec.third_party_id.outlet_sync_endpoint
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
                            sync_status = 'fail'
                            if status_code == 1 and 'data' in response:
                                rec.sync_id = response['data']
                    message = "Outlet Data Sync Failed: <b>%s</b>" % \
                              rec.third_party_id.name
                    if api_call.request_status == '200':
                        success = True
                        response = literal_eval(api_call.request_response)
                        status_code = response.get('code')
                        if status_code == 1:
                            # create sync log message
                            for field_string, field_value \
                                    in tracking_chatter_value.items():
                                field_msg += field_string + ': ' + \
                                             str(field_value) + '<br/>'
                            message = \
                                "Outlet Data Sync: <b>%s</b><br/><br/>%s" % \
                                (rec.third_party_id.name, field_msg)
                            sync_status = 'success'
                            rec.last_sync_info = last_sync_info
                    if not success:
                        session = ConnectorSession(self.env.cr,
                                                   self.env.user.id,
                                                   context=self.env.context)
                        _recall_api.delay(
                            session,
                            'third.party.outlet.sync',
                            rec.id,
                            'sync_data',
                            eta=60 * company.repeat_attempts_count)
                    # create sync log
                    sync_log_obj.create({
                        'sync_datetime': datetime.now(),
                        'sync_info': message,
                        'sync_status': sync_status,
                        'rec_id': rec.outlet_id.code,
                        'rec_name': rec.outlet_id.name,
                        'third_party_id': self.env.ref(
                            'baskin_integration_mobile.third_party_fugumobile').id
                    })
                self.env.cr.commit()
            except Exception:
                raise UserError(_('Something is not right with outlet %s. '
                                  'Kindly check the outlet configuration.') %
                                rec.outlet_id.name)
        return super(ThirdPartyOutletSync, self).sync_data()


class ThirdPartyMenuSync(models.Model):
    _inherit = "third.party.menu.sync"

    @api.multi
    def sync_data(self):
        """
        Sync the menu data to Mobile Apps
        """
        # todo: This is not neeeded in phase 1
        # for rec in self:
        #     # todo: call Mobile Apps API to update
        #     if rec.third_party_id.is_mobile_apps:
        #         # fields to sync back to Mobile Apps
        #         tracking_fields = ['name', 'active']
        #         # message to be shown in chatter log
        #         field_msg = ''
        #         # dictionary (key: Field String, value: Field Value)
        #         tracking_value = OrderedDict()
        #         for field in tracking_fields:
        #             field_attribute = rec.menu_id.fields_get(field)
        #             string = field_attribute[field].get('string')
        #             value = getattr(rec.menu_id, field)
        #             if field_attribute[field].get('type') == 'many2one':
        #                 value = value.name_get()[0][1]
        #             elif field_attribute[field].get('type') == 'selection':
        #                 value = dict(
        #                     rec.menu_id._fields[field].selection).get(value)
        #             tracking_value[string] = value
        #
        #         # call update API
        #         if rec.sync_id:
        #             pass
        #         # call create API
        #         else:
        #             pass
        #
        #         # create mail message in chatter log
        #         for field_string, field_value in tracking_value.items():
        #             field_msg += field_string + ': ' + str(field_value) + '<br/>'
        #         message = "Menu Data Sync: <b>%s</b><br/><br/>%s" % \
        #                   (rec.third_party_id.name, field_msg)
        #         rec.menu_id.message_post(body=message)
        return super(ThirdPartyMenuSync, self).sync_data()


class ThirdPartyMember(models.Model):
    _inherit = 'third.party.member'

    @api.model
    def get_member_data_mobile(self, phone_number):
        """ return member information based on the member code provided """
        # the phone number will be hashed in javascript
        # call the third party query member function
        mobile_app_party_id = self.env.ref('baskin_integration_mobile.third_party_fugumobile').id
        third_party = self.env['third.party'].browse(mobile_app_party_id)
        member = third_party.with_context(phone=True).\
            query_member(phone_number)
        if member:
            return {
                'id': member.id,
                'name': member.name,
                'code': member.code,
                'third_party_id': member.third_party_id.id,
            }

    @api.multi
    def opt_out(self):
        """ perform the mobile app member opt out action
        """
        res = super(ThirdPartyMember, self).opt_out()
        for rec in self:
            if rec.third_party_id.is_mobile_apps:
                # make the member's voucher expire
                vouchers = self.env['br.config.voucher'].search([
                    ('member_id', '=', rec.id),
                    ('status', '=', 'available'),
                    ('shared_voucher', '!=', True)])
                vouchers.write({
                    'status': 'expired'
                })
                # opt out the member
                rec.is_opt_out = True
        return res
