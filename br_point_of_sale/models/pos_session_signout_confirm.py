from openerp import models, api, fields, _
from datetime import datetime, timedelta


class PosSessionSignoutConfirmation(models.TransientModel):
    _name = 'pos.session.signout.confirm'

    @api.multi
    def action_confirm(self):
        session = self.env['pos.session'].browse(self.env.context.get('session_ids', []))
        session.signal_workflow('cashbox_control')
        return self.env.context.get('session_view', {'type': 'ir.actions.act_window_close'})

class PosSessionClosingConfirmation(models.TransientModel):
    _name = 'pos.session.closing.confirm'

    @api.multi
    def action_confirm(self):
        session = self.env['pos.session'].browse(self.env.context.get('session_ids', []))
        session.signal_workflow('close')
        return self.env.context.get('session_view', {'type': 'ir.actions.act_window_close'})

    @api.model
    def auto_close_rescue_pos(self):
        d = datetime.now().date() - timedelta(days=2)
        d1 = datetime.strftime(d, "%Y-%m-%d %H:%M:%S")
        rescue_session = self.env['pos.session'].search([('rescue', '=', True), ('state', '!=', 'closed'),
                                                         ('create_date', '<=', d1)])
        if rescue_session:
            for r in rescue_session:
                if r.state == 'opened':
                    r.signal_workflow('cashbox_control')
                    r.signal_workflow('close')
                elif r.state == 'closing_control':
                    r.signal_workflow('close')

class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.multi
    def button_signout_confirm(self):
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        view_id = ir_model_data.get_object_reference('br_point_of_sale', 'pos_session_signout_confirm_form')[1]
        ctx = self.env.context.copy()
        session_id = self.current_session_id.id
        ctx['session_ids'] = session_id
        ctx['session_view'] = self._open_session(session_id)
        # self.current_session_id.signal_workflow('cashbox_control')
        return {
            'name': _('Close Pos Session Confirmation'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'pos.session.signout.confirm',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'target': 'new',
            'context': ctx,
        }
