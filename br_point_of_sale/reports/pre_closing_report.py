from openerp import models, api, fields, _
from collections import OrderedDict
from datetime import datetime, timedelta
from openerp.exceptions import ValidationError, UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.multi
    def print_pre_closing_report(self):
        for session in self:
            if session.state == 'closed':
                raise ValidationError(_(
                    "BRReportMessage: You can not print Pre Closing Report when session is already closed and posted!"))
        return self.with_context(rp_name='pre_closing').get_x_report_data()
