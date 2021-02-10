# -*- coding: utf-8 -*-
from openerp import http
from openerp.http import request


class FieldOptions(http.Controller):

    @http.route(['/web/field/options'], type='json', auth='public')
    def check_field_options(self, **post):
        value = []
        model_obj = request.env['ir.model'].search([
            ('model', '=', post['model'])], limit=1)
        if model_obj:
            field_obj = request.env['ir.model.fields'].search([
                ('name', '=', post['field']),
                ('model_id', '=', model_obj.id)], limit=1)
            if field_obj:
                options_obj = request.env['ir.model.fields.options'].search([
                    ('model_id', '=', model_obj.id), ('field_id', '=', field_obj.id)])
                if options_obj:
                    if options_obj.no_open:
                        value.append({'no_open': True})
                    if options_obj.no_create:
                        value.append({'no_create': True})
                    if options_obj.no_create_edit:
                        value.append({'no_create_edit': True})
        return value