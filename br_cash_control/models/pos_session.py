import time
import psycopg2
from openerp import fields, models, api, SUPERUSER_ID, _
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)



class br_pos_session(models.Model):

    _inherit = 'pos.session'

    posted_cash_register_balance_end = fields.Float(string=_("Theoretical Closing Balance"), readonly=True)
    posted_cash_register_difference = fields.Float(string=_("Difference"), readonly=True)
    is_outlet_pic = fields.Boolean(compute='_check_is_outlet_pic')

    @api.model
    def _check_is_outlet_pic(self):
        outlet_pic = self.env['ir.model.data'].get_object('point_of_sale', 'group_pos_manager')
        user_groups = self.env.user.groups_id
        if outlet_pic:
            for session in self:
                session.is_outlet_pic = False
                for group in user_groups:
                    if group.id == outlet_pic.id:
                        session.is_outlet_pic = True
                        break

    # Override
    def wkf_action_close(self, cr, uid, ids, context=None):
        # Close CashBox
        local_context = dict(context)
        for record in self.browse(cr, uid, ids, context=context):
            # if record.cash_register_balance_end_real == 0 and record.rescue == 0:
            #     raise UserError(_("Real Closing Balance Should Not Be Equal To 0 !"))
            company_id = record.config_id.company_id.id
            local_context.update({'force_company': company_id, 'company_id': company_id})
            # Longdt: Save posted cash_register
            cash_register_values = {
                'posted_cash_register_balance_end': record.cash_register_balance_end,
                'posted_cash_register_difference': record.cash_register_difference,
            }
            self.write(cr, uid, [record.id], cash_register_values, context)
            for st in record.statement_ids:
                if abs(st.difference) > st.journal_id.amount_authorized_diff:
                    # The pos manager can close statements with maximums.
                    if not self.pool.get('ir.model.access').check_groups(cr, uid, "point_of_sale.group_pos_manager"):
                        raise UserError(_("Your ending balance is too different from the theoretical cash closing (%.2f), the maximum allowed is: %.2f. You can contact your manager to force it.") % (st.difference, st.journal_id.amount_authorized_diff))
                if (st.journal_id.type not in ['bank', 'cash']):
                    raise UserError(_("The type of the journal for your payment method should be bank or cash "))
                self.pool['account.bank.statement'].button_confirm_bank(cr, SUPERUSER_ID, [st.id], context=local_context)
        self._confirm_orders(cr, uid, ids, context=local_context)
        self.write(cr, uid, ids, {'state' : 'closed'}, context=local_context)
        obj = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'point_of_sale', 'menu_point_root')[1]
        return {
            'type' : 'ir.actions.client',
            'name' : 'Point of Sale Menu',
            'tag' : 'reload',
            'params' : {'menu_id': obj},
        }

    @api.model
    def check_close_session(self, session_id):
        if session_id:
            session_id = int(session_id)
            re = self.search_read([('id', '=', session_id), ('state', 'in', ('closed', 'closing_control'))])
            if len(re):
                return True
        return False