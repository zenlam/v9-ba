from openerp.osv import osv, fields
from openerp import tools, models, SUPERUSER_ID, _

from functools import partial
from openerp.exceptions import UserError

from openerp.addons.point_of_sale import point_of_sale


class br_pos_config(osv.osv):
    _inherit = 'pos.config'

    # Override
    def _get_last_session(self, cr, uid, ids, fieldnames, args, context=None):
        result = dict()

        for record in self.browse(cr, uid, ids, context=context):
            session_ids = self.pool['pos.session'].search_read(
                cr, uid,
                [('config_id', '=', record.id), ('state', '=', 'closed'),
                 ('rescue', '=', False)],
                ['cash_register_balance_end_real', 'stop_at'],
                order="stop_at desc", limit=1, context=context)
            if session_ids:
                result[record.id] = {
                    'last_session_closing_cash': session_ids[0]['cash_register_balance_end_real'],
                    'last_session_closing_date': session_ids[0]['stop_at'],
                }
            else:
                result[record.id] = {
                    'last_session_closing_cash': 0,
                    'last_session_closing_date': None,
                }
        return result

class br_pos_session(osv.osv):
    _inherit = 'pos.session'

    # OVERRIDE
    def create(self, cr, uid, values, context=None):
        context = dict(context or {})
        config_id = values.get('config_id', False) or context.get('default_config_id', False)
        if not config_id:
            raise UserError(_("You should assign a Point of Sale to your session."))

        # journal_id is not required on the pos_config because it does not
        # exists at the installation. If nothing is configured at the
        # installation we do the minimal configuration. Impossible to do in
        # the .xml files as the CoA is not yet installed.
        jobj = self.pool.get('pos.config')
        pos_config = jobj.browse(cr, uid, config_id, context=context)
        context.update({'company_id': pos_config.company_id.id})
        is_pos_user = self.pool['res.users'].has_group(cr, uid, 'point_of_sale.group_pos_user')
        if not pos_config.journal_id:
            jid = jobj.default_get(cr, uid, ['journal_id'], context=context)['journal_id']
            if jid:
                jobj.write(cr, SUPERUSER_ID, [pos_config.id], {'journal_id': jid}, context=context)
            else:
                raise UserError(_("Unable to open the session. You have to assign a sale journal to your point of sale."))

        # define some cash journal if no payment method exists
        if not pos_config.journal_ids:
            journal_proxy = self.pool.get('account.journal')
            cashids = journal_proxy.search(cr, uid, [('journal_user', '=', True), ('type','=','cash')], context=context)
            if not cashids:
                cashids = journal_proxy.search(cr, uid, [('type', '=', 'cash')], context=context)
                if not cashids:
                    cashids = journal_proxy.search(cr, uid, [('journal_user','=',True)], context=context)

            journal_proxy.write(cr, SUPERUSER_ID, cashids, {'journal_user': True})
            jobj.write(cr, SUPERUSER_ID, [pos_config.id], {'journal_ids': [(6,0, cashids)]})

        statements = []
        create_statement = partial(self.pool['account.bank.statement'].create, cr, is_pos_user and SUPERUSER_ID or uid)
        is_rescue_sesion = values.get('rescue', False)
        for journal in pos_config.journal_ids:
            # set the journal_id which should be used by
            # account.bank.statement to set the opening balance of the
            # newly created bank statement
            context['journal_id'] = journal.id if pos_config.cash_control and journal.type == 'cash' and not journal.is_rounding_method else False

            if pos_config.cash_control and journal.type == 'cash' and not journal.is_rounding_method and not is_rescue_sesion:
                balance_start = pos_config._get_last_session(cr, uid)[config_id]['last_session_closing_cash']
            else:
                balance_start = 0
            st_values = {
                'journal_id': journal.id,
                'user_id': uid,
                # Longdt start
                'balance_start': balance_start,
            }
            statements.append(create_statement(st_values, context=context))

        unique_name = self.pool['ir.sequence'].next_by_code(cr, uid, 'pos.session', context=context)
        if values.get('name'):
            unique_name += ' ' + values['name']

        values.update({
            'name': unique_name,
            'statement_ids': [(6, 0, statements)],
            'config_id': config_id
        })

        return super(point_of_sale.pos_session, self).create(cr, is_pos_user and SUPERUSER_ID or uid, values, context=context)