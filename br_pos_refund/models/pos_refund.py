# --*-- coding: utf-8 --*--
from openerp import fields, models, api, _
from openerp.exceptions import UserError
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
import time

class br_refund_request_wizard(models.TransientModel):
    _name = 'br.confirm.refund.request.wizard'

    remarks = fields.Text('Remarks', required=True)

    @api.multi
    def request_cancel(self):
        ids = self.env.context.get('active_ids', [])
        if ids:
            order = self.env['pos.order'].browse(ids[0])
            order.state = 'cancellation_requested'
            order.cancel_request_remark = self.remarks
        else:
            raise UserError(_("Do not found any active order to request cancel !"))


class br_refund_wizard(models.TransientModel):
    _name = 'br.confirm.refund.wizard'

    @api.model
    def _get_active_id(self):
        ids = self.env.context.get('active_ids', [])
        if ids:
            return self.env['pos.order'].browse(ids[0])
        else:
            return False



    @api.model
    def _get_remark(self):
        ids = self.env.context.get('active_ids', [])
        if ids:
            return self.env['pos.order'].browse(ids[0]).cancel_request_remark
        else:
            return False

    pos_order_id = fields.Many2one('pos.order', string="POS Order", default=_get_active_id)
    remarks = fields.Text('Remarks', required=True, default=_get_remark)

    @api.multi
    def refund(self):
        """Create a copy of order  for refund order"""
        if self.pos_order_id:
            order = self.pos_order_id
            if order.is_refund or order.is_refunded:
                raise UserError(_("This receipt is already cancelled, please check your order list again!"))
            # if any payment method of this order is being removed from the
            # outlet, block the receipt cancellation.
            available_payment_methods = order.config_id.journal_ids.ids
            for statement in order.statement_ids:
                if statement.journal_id.id not in available_payment_methods:
                    raise UserError(_(
                        '%s in this order has already been removed from this '
                        'POS Config. Please add the payment method before '
                        'proceeding with the refeipt cancellation.'
                        '\n Note: Please remember to remove the payment '
                        'method after the receipt cancellation has been '
                        'approved.') % statement.journal_id.name)

            current_session_ids = self.env['pos.session'].search([
                ('state', '!=', 'closed'),
                #('user_id', '=', self.env.user.id),
                ('outlet_id', '=', self.pos_order_id.outlet_id.id)])
            if not current_session_ids:
                raise UserError(
                    _('You cannot approve this receipt cancellation request as there is no active session for this outlet. Please open a new session to approve this request.'))

            wh = order.outlet_id.warehouse_id

            clone_id = order.with_context(refund=True).copy({
                'name': order.name + ' REFUND',  # not used, name forced by create
                'session_id': current_session_ids[0].id,
                'date_order': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'pos_reference': 'REFUND ' + order.pos_reference,
                'location_id': wh and wh.lot_stock_id and wh.lot_stock_id.id or False,
                'is_refund': True,
                'parent_id': order.id,
                'note': self.remarks

            })
            if order.account_move:
                order.write({'is_refunded': True, 'refund_order_id': clone_id.id, 'state': 'done'})
            else:
                order.write({'is_refunded': True, 'refund_order_id': clone_id.id, 'state': 'paid'})

            if self.env.context.get('auto'):
                return clone_id

            abs = {
                'name': _('Return Products'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'pos.order',
                'res_id': clone_id.id,
                'view_id': False,
                'context': self.env.context,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }
            return abs


class br_pos_refund(models.Model):
    _inherit = 'pos.order'

    is_refund = fields.Boolean(string='Is Refund', default=False, help="Is Refund Order")
    is_refunded = fields.Boolean(string='Is Refunded', default=False, help="Is Order Refunded")
    parent_id = fields.Many2one(comodel_name='pos.order')
    refund_order_id = fields.Many2one(comodel_name='pos.order', help='Refund receipt')
    state = fields.Selection(selection_add=[('cancellation_requested', 'Cancellation Requested'), ('cancellation_approved', 'Cancellation Approved')])
    is_session_closed = fields.Boolean(string="Is Session Closed", compute='_check_session_closed')
    cancel_request_remark = fields.Text('Remarks')

    @api.multi
    def _check_session_closed(self):
        """
        Check if order's session is closed or not
        :return:
        """
        for order in self:
            order.is_session_closed = order.session_id.state == 'closed'

    @api.multi
    def action_cancellation_requested(self):
        """
        Request cancellation for order belongs to closed session
        :return:
        """
        for order in self.filtered(lambda x: x.state not in ('cancellation_requested', 'cancel_approve')):
            if order.vouchers:
                raise UserError(_("This order has voucher(s) applied. Receipt cancellation is not allowed for orders with coupon/voucher applied."))
            if order.session_id.state != 'closed':
                raise UserError(_("Your session is still opening, you can not cancel order directly !"))

            abs = {
                'name': _('Receipt Cancellation Request'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'br.confirm.refund.request.wizard',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
            return abs


    @api.multi
    def action_approve_cancel_request(self):
        """
        Approve cancel order request
        :return:
        """
        for order in self.filtered(lambda x: x.state == 'cancellation_requested'):
            order.state = 'cancellation_approved'
            order.with_context(auto=True).confirm_refund()
            refund_id = self.env['br.confirm.refund.wizard'].create({
                'pos_order_id': order.id,
                'remarks': order.cancel_request_remark,
            })
            refund_order_id = refund_id.with_context(auto=True).sudo(order.user_id).refund()

            Payment = self.env['pos.make.payment']

            if order.statement_ids:
                # put loop here to handle rounding and multiple payment method
                journal_paid = []
                for statement in order.statement_ids:
                    if statement.journal_id in journal_paid:
                        continue
                    journal_id = statement.journal_id
                    amount = sum(-smt.amount for smt in order.statement_ids if smt.journal_id == statement.journal_id)
                    payment_id = Payment.with_context(active_id=refund_order_id.id).create({
                        'journal_id': journal_id.id,
                        'amount': amount if amount else 0.00,
                        'payment_date': datetime.now().date()
                    })
                    payment_id.sudo(order.user_id).check()
                    journal_paid.append(statement.journal_id)

                    # if order is fully paid then break the loop
                    if refund_order_id.test_paid():
                        break
            else:
                # Handle order without payment
                default_refund_journal = self.env['account.journal'].search([
                    ('is_default_refund', '=', True)], limit=1).id
                if not default_refund_journal:
                    raise UserError(_(
                        'Please configure a default refund payment method'
                        ' (Retail Cash) to proceed!'))
                payment_id = Payment.with_context(active_id=refund_order_id.id).create({
                    'journal_id': default_refund_journal,
                    'amount': 0.00,
                    'payment_date': datetime.now().date()
                })
                payment_id.sudo(order.user_id).check()

    @api.multi
    def action_refuse_cancel_request(self):
        """
        Refuse to cancel receipt
        :return:
        """
        for order in self.filtered(lambda x: x.state == 'cancellation_requested'):
            order.state = 'done'

    @api.multi
    def confirm_refund(self):
        if self.vouchers:
            raise UserError(_("This order has voucher(s) applied. Receipt cancellation is not allowed for orders with coupon/voucher applied."))
        if self.session_id.state == 'closed' and self.state != 'cancellation_approved':
            raise UserError(_("You cannot cancel an order after the session is closed. Please contact HQ if needed!"))
        # add context to skip returning wizard
        if self.env.context.get('auto'):
            return

        abs = {
            'name': _('Confirm receipt cancellation'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'br.confirm.refund.wizard',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
        return abs
