# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.exceptions import UserError

DATETIME_FORMAT_1 = '%m%d%Y%H%M%S'
DATETIME_FORMAT_2 = '%y%m%d%H%M%S'


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _payment_fields(self, cr, uid, ui_paymentline, context=None):
        """ Extend the dictionary of payment with the card info """
        res = super(PosOrder, self)._payment_fields(cr, uid, ui_paymentline,
                                                    context=context)
        if ui_paymentline.get('approval_no', False):
            transc_datetime = ui_paymentline.get('transaction_date') + \
                              ui_paymentline.get('transaction_time')
            payment_method = self.pool.get('account.journal').browse(
                cr, uid, ui_paymentline['journal_id'], context)
            if payment_method.edc_terminal in \
                    ('cimb_bonusPoint', 'cimb_ewallet'):
                transc_datetime_datetime = datetime.strptime(transc_datetime,
                                                             DATETIME_FORMAT_2)
            else:
                transc_datetime_datetime = datetime.strptime(transc_datetime,
                                                             DATETIME_FORMAT_1)
            res.update(
                approval_no=ui_paymentline.get('approval_no'),
                terminal_id=ui_paymentline.get('terminal_id'),
                card_number=ui_paymentline.get('card_number'),
                card_type=ui_paymentline.get('card_type'),
                transaction_inv_number=ui_paymentline.get(
                    'transaction_inv_number'),
                transaction_datetime=transc_datetime_datetime,
                merchant_id=ui_paymentline.get('merchant_id'),
                acquirer_name=ui_paymentline.get('acquirer_name'),
                acquirer_code=ui_paymentline.get('acquirer_code'),
                settlement_batch_number=ui_paymentline.get(
                    'settlement_batch_number')
            )
        return res

    @api.model
    def add_payment(self, order_id, data):
        """ Update card info for statement line"""
        statement_id = super(PosOrder, self).add_payment(order_id, data)
        if 'transaction_datetime' in data and data['transaction_datetime']:
            statement_line = self.env['account.bank.statement.line'].search(
                [('statement_id', '=', statement_id),
                 ('pos_statement_id', '=', order_id),
                 ('journal_id', '=', data['journal']),
                 ('amount', '=', data['amount'])], limit=1)
            statement_line.write({
                'approval_no': data.get('approval_no'),
                'terminal_id': data.get('terminal_id'),
                'card_number': data.get('card_number'),
                'card_type': data.get('card_type'),
                'transaction_inv_number': data.get('transaction_inv_number'),
                'transaction_datetime': data.get('transaction_datetime'),
                'merchant_id': data.get('merchant_id'),
                'acquirer_name': data.get('acquirer_name'),
                'acquirer_code': data.get('acquirer_code'),
                'settlement_batch_number': data.get('settlement_batch_number')
            })
        return statement_id
