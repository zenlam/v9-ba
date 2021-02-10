# -*- coding: utf-8 -*-
from openerp import http
from openerp.http import request


class FieldOptions(http.Controller):

    @http.route(['/web/model/hide_duplicate'], type='json', auth='public')
    def check_field_options(self, **post):
        options_obj = request.env['web.hide.duplicate'].search([
            ('model_id.model', '=', post['model']), ('hide_duplicate', '=', True)])
        if options_obj:
            return True
        else:
            return False
