# -*- coding: utf-8 -*-
from openerp import fields, models, api, _
from openerp.exceptions import UserError, ValidationError


class pos_payment(models.TransientModel):
    _inherit = 'pos.make.payment'

    def get_journal_id(self, cr, uid, order, context=None):
        ref = order.pos_reference
        if ref and 'REFUND' in ref:
            origin = ref.replace("REFUND ", "")
            order_pool = self.pool.get('pos.order')
            prev_order_id = order_pool.search(cr, uid, [('pos_reference', '=', origin)], context=context)
            if prev_order_id:
                prev_order = order_pool.browse(cr, uid, prev_order_id, context=context)
                normal_journal = False
                rounding_journal = False
                remaining_amount = order.amount_total - order.amount_paid
                prev_rounding_total = 0.0
                for statement in prev_order[0].statement_ids:
                    if statement.journal_id.is_rounding_method == True:
                        prev_rounding_total += statement.amount
                        rounding_journal = statement.journal_id.id
                    if statement.journal_id.is_rounding_method == False:
                        normal_journal = statement.journal_id.id
                if abs(round(prev_rounding_total,2)) == abs(round(remaining_amount,2)):
                    return rounding_journal
                else:
                    return normal_journal
        else:
            session = order.session_id
            if session:
                for journal in session.config_id.journal_ids:
                    return journal.id
        return False

    def _default_journal(self, cr, uid, context=None):
        if not context:
            context = {}
        order_obj = self.pool.get('pos.order')
        active_id = context and context.get('active_id', False)
        if active_id:
            order = order_obj.browse(cr, uid, active_id, context=context)
            journal_id = self.get_journal_id(cr, uid, order, context=context)
            return journal_id
        return False

    def _default_amount(self, cr, uid, context=None):
        order_obj = self.pool.get('pos.order')
        active_id = context and context.get('active_id', False)
        if active_id:
            order = order_obj.browse(cr, uid, active_id, context=context)

            ref = order.pos_reference
            if ref and 'REFUND' in ref:
                origin = ref.replace("REFUND ", "")
                order_pool = self.pool.get('pos.order')
                prev_order_id = order_pool.search(cr, uid, [('pos_reference', '=', origin)], context=context)
                if prev_order_id:
                    prev_order = order_pool.browse(cr, uid, prev_order_id, context=context)
                    rounding_total = 0.0
                    for statement in prev_order[0].statement_ids:
                        if statement.journal_id.is_rounding_method == True:
                            rounding_total += statement.amount

                    if abs(round(order.amount_total - order.amount_paid,2)) == abs(round(rounding_total,2)):
                        return order.amount_total - order.amount_paid
                    else:
                        return (order.amount_total - order.amount_paid) + rounding_total
            else:

                return order.amount_total - order.amount_paid
        return False

    _defaults = {
        'journal_id': _default_journal,
        'amount': _default_amount,
    }


class account_journal(models.Model):
    _inherit = 'account.journal'

    pos_config_ids = fields.Many2many('pos.config', 'pos_config_journal_rel', 'journal_id', 'pos_config_id', string=_("Pos Configs"))

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        args = args or []
        if context.get('filter_session_journal', False):
            pos_session_id = context.get('pos_session_id', False)
            session = self.pool.get('pos.session').browse(cr, uid, pos_session_id, context=context)
            if session:
                journal_ids = [journal.id for journal in session.journal_ids]
                args.append(('id', 'in', journal_ids))
        return super(account_journal, self).name_search(cr, uid, name, args=args, operator=operator, context=context,
                                                        limit=limit)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        if self.env.context.get('filter_session_journal', False):
            pos_session_id = self.env.context.get('pos_session_id', False)
            session = self.env['pos.session'].browse(pos_session_id)
            if session:
                journal_ids = [journal.id for journal in session.journal_ids]
                args.append(('id', 'in', journal_ids))
        return super(account_journal, self).search(args, offset=offset, limit=limit, order=order, count=count)

    @api.multi
    def write(self, vals):
        for rec in self:
            if 'pos_config_ids' in vals:
                # get the removed pos config id
                remove_pos_config = [
                    config for config in rec.pos_config_ids.ids
                    if config not in vals['pos_config_ids'][0][2]]
                # raise warning if the removed pos config has any unposted
                # transaction using the current payment method
                if remove_pos_config:
                    unposted_transaction = self.env['pos.order'].search([
                        ('config_id', 'in', remove_pos_config),
                        ('state', 'not in', ['done', 'cancel'])])
                    restricted_config = []
                    for transaction in unposted_transaction:
                        for statement in transaction.statement_ids:
                            if statement.journal_id.id == rec.id:
                                restricted_config.append(
                                    transaction.config_id.name)
                    if restricted_config:
                        raise ValidationError(_(
                            'There are still orders/receipt '
                            'cancellations with this payment method '
                            'that have not been posted yet. Please '
                            'post all orders/receipt cancellations '
                            'before removing the POS config from this '
                            'payment method:\n %s'
                        ) % '\n'.join(restricted_config))
        return super(account_journal, self).write(vals)