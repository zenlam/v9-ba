# -*-coding: utf-8 -*-
from openerp import fields, models, api, _
from openerp.addons.account.wizard.pos_box import CashBox

# class BoxAccount(CashBox):
#     _register = False

class pos_session(models.Model):
    _inherit = 'pos.session'
    cash_box_out_ids = fields.Many2many('cash.box.out', 'pos_session_cash_out', 'pos_session_id', 'cash_out_id',
                                        copy=False)
    cash_box_in_ids = fields.Many2many('cash.box.in', 'pos_session_cash_in', 'pos_session_id', 'cash_in_id', copy=False)

# TODO: Should make an interface for cash.box.in and cash.box.out to avoid duplicate code ?
class box_account_in(models.Model):
    _inherit = 'cash.box.in'

    cash_control = fields.Many2one(string=_('Cash control'), comodel_name='br.cash.control', required=True)
    pos_session_ids = fields.Many2many('pos.session', 'pos_session_cash_in', 'cash_in_id', 'pos_session_id', copy=False)

    @api.model
    def default_get(self, fields):
        result = super(box_account_in, self).default_get(fields)
        result.update(pos_session_ids=[(6, 0, self.env.context.get('active_ids'))])
        return result

    # Override
    @api.one
    def _calculate_values_for_statement_line(self, record):
        values = super(box_account_in, self)._calculate_values_for_statement_line(record)
        if self.cash_control and self.cash_control.debit_account_id:
            values[0].update(
                account_id=self.cash_control.credit_account_id.id,
                credit_account_id=self.cash_control.debit_account_id.id,
                name='{0}: {1}'.format(self.cash_control.name, self.name),
                cash_control_id=self.cash_control.id
            )
        return values[0]

    # Override
    @api.multi
    def run(self):
        res = super(box_account_in, self).run()
        # active_model = self.env.context.get('active_model', False) or False
        # active_ids = self.env.context.get('active_ids', []) or []
        # if active_model == 'pos.session':
        #     records = self.env[active_model].search([('id', 'in', active_ids)])
        #     for record in records:
        #         for st_line in record.cash_register_id.line_ids:
        #             if st_line.pos_statement_id:
        #                 st_line.fast_counterpart_creation()
        return res

class box_account_out(models.Model):
    _inherit = 'cash.box.out'

    cash_control = fields.Many2one(string=_('Cash control'), comodel_name='br.cash.control', required=True)
    pos_session_ids = fields.Many2many('pos.session', 'pos_session_cash_out', 'cash_out_id', 'pos_session_id',
                                       copy=False)

    @api.model
    def default_get(self, fields):
        result = super(box_account_out, self).default_get(fields)
        result.update(pos_session_ids=[(6, 0, self.env.context.get('active_ids'))])
        return result

    # Override
    @api.one
    def _calculate_values_for_statement_line(self, record):
        values = super(box_account_out, self)._calculate_values_for_statement_line(record)
        if self.cash_control and self.cash_control.debit_account_id:
            values[0].update(
                account_id=self.cash_control.debit_account_id.id,
                credit_account_id=self.cash_control.credit_account_id.id,
                name='{0}: {1}'.format(self.cash_control.name, self.name),
                cash_control_id=self.cash_control.id
            )
        return values[0]

    # Override
    @api.multi
    def run(self):
        res = super(box_account_out, self).run()
        # active_model = self.env.context.get('active_model', False) or False
        # active_ids = self.env.context.get('active_ids', []) or []
        # if active_model == 'pos.session':
        #     records = self.env[active_model].search([('id', 'in', active_ids)])
        #     for record in records:
        #         for st_line in record.cash_register_id.line_ids:
        #             if st_line.pos_statement_id:
        #                 st_line.fast_counterpart_creation()
        return res
