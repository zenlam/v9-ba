from openerp import api, models, fields, _
from openerp.exceptions import UserError, ValidationError
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class ir_ui_menu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        if self.env.user.has_group('base.kpmg_auditor'):
            args.append(('id', 'not in', [self.env.ref('mail.mail_channel_menu_root_chat').id, self.env.ref('calendar.mail_menu_calendar').id]))
        res = super(ir_ui_menu, self).search(args, offset=offset, limit=limit, order=order, count=count)
        return res