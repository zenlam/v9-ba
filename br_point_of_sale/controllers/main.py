# -*- coding: utf-8 -*-
from openerp import http
from openerp.addons.web.http import Controller, route, request
from openerp.addons.report.controllers.main import ReportController
from openerp.addons.point_of_sale.controllers.main import PosController
import werkzeug.utils
import json


class BrReportController(ReportController):

    @route(['/report/download'], type='http', auth="user")
    def report_download(self, data, token):
        res = super(BrReportController, self).report_download(data, token)
        try:
            message_data = json.loads(werkzeug.utils.unescape(res.data))
            if "data" in message_data:
                message = message_data["data"].get("message", "")
                if message.find("BRReportMessage:") >= 0:
                    _message = message.replace("BRReportMessage:", "").replace("None", "")
                    message = {
                        'code': 200,
                        'message': _message,
                        'data': _message
                    }
                    return request.make_response(werkzeug.utils.escape(json.dumps(message)))
        except Exception, e:
            pass
        return res


class BrPosController(PosController):

    @http.route('/pos/web', type='http', auth='user')
    def a(self, debug=False, **k):
        cr, uid, context, session = request.cr, request.uid, request.context, request.session

        # if user not logged in, log him in
        PosSession = request.registry['pos.session']
        pos_session_ids = PosSession.search(cr, uid, [('state', '=', 'opened'), ('user_id', '=', session.uid)], context=context)
        if not pos_session_ids:
            return werkzeug.utils.redirect('/web#action=point_of_sale.action_client_pos_menu')
        PosSession.login(cr, uid, pos_session_ids, context=context)
        request.login_number = PosSession.browse(cr, uid, pos_session_ids, context=context).login_number
        return request.render('point_of_sale.index')