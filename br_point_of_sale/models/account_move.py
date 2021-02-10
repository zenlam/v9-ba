# TODO: Create new package for this class
from openerp import api, models, fields, tools
from datetime import datetime, timedelta
import re


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, vals):
        """Update date using start date from pos.session"""
        pos_session = self.get_pos_session(vals)
        if pos_session:
            start_at_datetime = datetime.strptime(pos_session.start_at, tools.DEFAULT_SERVER_DATETIME_FORMAT)
            # add 8 hours due to timezone
            start_at_datetime += timedelta(hours=8)
            dt = start_at_datetime.strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            vals.update(date=dt)
        return super(AccountMove, self).create(vals)

    def get_pos_session(self, vals):
        pos_session = None
        if 'statement_line_id' in vals:
            stml_obj = self.env['account.bank.statement.line'].browse(vals['statement_line_id'])
            if stml_obj.statement_id and stml_obj.statement_id.pos_session_id:
                pos_session = stml_obj.statement_id.pos_session_id
        elif 'ref' in vals:
            pos_session = self.env['pos.session'].search([('name', '=', vals['ref'])])
            if not pos_session:
                pos_order = self.env['pos.order'].search([('name', '=', vals['ref'])])
                if not pos_order:
                    picking = self.env['stock.picking'].search([('name', '=', vals['ref'])])
                    pos_order = self.env['pos.order'].search([('name', '=', picking.origin)])
                if pos_order:
                    pos_session = pos_order.session_id
        if pos_session and pos_session.rescue:
            pattern = "RESCUE FOR (.+?)\)"
            match = re.search(pattern, pos_session.name)
            if match:
                # Must reset pos_session, investigate more
                pos_session = None
                session_name = match.group(1)
                pos_session = self.env['pos.session'].search([('name', '=', session_name)])
        return pos_session
