# -*- coding: utf-8 -*-

from openerp import http
from openerp.addons.restful.common import (
    extract_arguments,
    invalid_response,
    valid_response,
)
from openerp.http import request
from openerp.addons.restful.controllers.main import validate_token
from openerp.addons.restful.controllers.main import generate_api_log
from openerp.addons.restful.controllers.main import APIController

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


class MemberApiController(APIController):

    @generate_api_log
    @validate_token
    @http.route("/api/fugu/member", type="http", auth="none", methods=["POST"],
                csrf=False)
    def create_member(self, **payload):
        """ Create member based on the payload.
        Payload Content:
        1. Member Code
        2. Member Name
        3. Member Level
        :return: Member creation message
        """
        # get the member data from the payload
        member_code = payload.get('member_code')
        member_name = payload.get('name')
        member_level = payload.get('member_level')

        # return invalid response if member code is not provided
        if not member_code:
            return invalid_response(
                "No Member Code",
                "Kindly provide a Member Code for the member creation.",
                400
            )

        # return invalid response if member name is not provided
        if not member_name:
            return invalid_response(
                "No Member Name",
                "Kindly provide a Member Name for the member creation.",
                400
            )

        # return invalid response if member level is not provided
        if not member_level:
            return invalid_response(
                "No Member Level",
                "Kindly provide a Member Level for the member creation.",
                400
            )

        success_response = {
            'result': 'Success'
        }

        # check if the member code already exists in system.
        exist_member = request.env['third.party.member'].search([
            ('code', '=', member_code)])
        # return Success if the details are matched, else return Error
        if exist_member:
            if exist_member.name == member_name and \
                    exist_member.member_level == member_level:
                return valid_response(success_response)
            else:
                return invalid_response(
                    "Member Exists"
                    "Member already exists with different information.",
                    400
                )

        # create member record based on the vals
        vals = {
            'code': member_code,
            'name': member_name,
            'member_level': member_level,
            'third_party_id': request.env.ref(
                'baskin_integration_mobile.third_party_fugumobile').id
        }
        try:
            request.env['third.party.member'].sudo().create(vals)
        except Exception as e:
            return invalid_response(
                "Error in Creating Member",
                str(e),
                405
            )
        return valid_response(success_response)

    @generate_api_log
    @validate_token
    @http.route("/api/fugu/member", type="http", auth="none", methods=["PUT"],
                csrf=False)
    def edit_member(self, **payload):
        """ Edit member based on the payload.
        Payload Content:
        1. Member Code
        2. Fields to update
        :return: Status Code
        """
        # get the member data from the payload
        member_code = payload.get('member_code')
        # remove the member_code key value pair from the payload
        del payload['member_code']
        # get the vals to be written into the record
        vals = payload

        member_id = request.env['third.party.member'].sudo().search(
            [('code', '=', member_code)], limit=1
        )

        # return invalid response if member id is not found in the system
        if not member_code or not member_id:
            return invalid_response(
                "Invalid Member ID",
                "This Member ID is not found in the system.",
                400
            )

        origin_fields = [key for key, field in member_id._fields.items()]
        update_fields = [key for key, field in vals.items()]

        # return invalid response if a field to update is not found
        unknown_field = set(update_fields) - set(origin_fields)
        if unknown_field:
            return invalid_response(
                "Invalid Field",
                "This field is not valid %s" % ', '.join(unknown_field),
                400
            )

        # update the record
        try:
            member_id.sudo().write(vals)
        except Exception as e:
            return invalid_response(
                "Error in Updating Member",
                str(e),
                405
            )
        response = {
            'result': 'Success'
        }
        return valid_response(response)

    @generate_api_log
    @validate_token
    @http.route("/api/fugu/memberoptout", type="http", auth="none",
                methods=["PUT"], csrf=False)
    def opt_out_member(self, **payload):
        """ Perform member opt out based on the payload.
        Payload Content:
        1. Member Code
        :return: Status Code
        """
        # get the member data from the payload
        member_code = payload.get('member_code')

        # get the member record
        member_id = request.env['third.party.member'].sudo().search(
            [('code', '=', member_code)], limit=1
        )

        # return invalid response if member id is not found in the system
        if not member_code or not member_id:
            return invalid_response(
                "Invalid Member ID",
                "This Member ID is not found in the system.",
                400
            )

        # update the record
        try:
            member_id.sudo().opt_out()
        except Exception as e:
            return invalid_response(
                "Error in Opting Out Member",
                str(e),
                405
            )
        response = {
            'result': 'Success'
        }
        return valid_response(response)