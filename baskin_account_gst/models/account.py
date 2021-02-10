# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError


class GSTMapping(models.Model):
    _name = 'gst.mapping'

    name = fields.Char('Name', required=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, 
                                 default=lambda self: self.env['res.company']._company_default_get('gst.mapping'))
    


class GSTTaxMapping(models.Model):
    _name = 'gst.tax.mapping'
    
    name = fields.Many2one('gst.mapping', string='GST Column')
    taxes_ids = fields.Many2many(
                'account.tax',
                'gst_mapping_account_tax_rel',
                'gst_mapping_id',
                'tax_id',
                string='Tax code')
    tax_type = fields.Selection([
        ('input', 'Input'),
        ('output', 'Output'),], string='Type')
    is_base = fields.Boolean('Base')
    is_formula = fields.Boolean('Is Formula?')
    from_gst_mapping_ids = fields.Many2many(
                            'gst.mapping',
                            'gst_mapping_from_rel',
                            'from_gst_mapping_id',
                            'gst_mapping_id',
                            string='From')
    to_gst_mapping_ids = fields.Many2many(
                            'gst.mapping',
                            'gst_mapping_to_rel',
                            'to_gst_mapping_id',
                            'gst_mapping_id',
                            string='To',)
    operator = fields.Selection([
                    ('-', '-'),
                    ('+', '+'),
                    ('*', '*'),
                    ('/', '/')],
                    string='Operator')
    is_carry_forward_refund = fields.Boolean('Do you choose the carry forward refund?')
    carry_forward_refund = fields.Selection([
                                ('yes', 'Yes'),
                                ('no', 'No')], string='Carry Forward Value',
                                default='no')
    is_msic = fields.Boolean('Is MSIC?')
    msic_code = fields.Char('MSIC Code')
    data_gst_mapping_id = fields.Many2one('gst.mapping', 'Data to show in MSIC Code')
    is_tap_file = fields.Selection([
                    ('yes', 'Yes'),
                    ('no', 'No')],
                    string='Tap File',
                    required=True,
                    default='no')
    sequence = fields.Integer('GST Column Sequence')
    value_sequence = fields.Integer('MISC Code Sequence')
    company_id = fields.Many2one('res.company', 'Company', required=True, 
                                 default=lambda self: self.env['res.company']._company_default_get('gst.tax.mapping'))

    @api.constrains('sequence', 'value_sequence')
    def _check_sequence(self):
        for rec in self:
            if rec.sequence <= 0 and rec.is_tap_file == 'yes' or rec.value_sequence <= 0 and rec.is_msic:
                raise UserError(_('Sequence must be greater than zero!'))

            if rec.sequence > 0:
                seq_records = self.search([
                    '|',
                    ('sequence', '=', rec.sequence),
                    ('value_sequence', '=', rec.sequence),
                    ('id', '!=', rec.id)
                ])
                if seq_records:
                    raise UserError(_('You cannot have same sequence!'))

            if rec.value_sequence > 0:
                val_seq_records = self.search([
                    '|',
                    ('sequence', '=', rec.value_sequence),
                    ('value_sequence', '=', rec.value_sequence),
                    ('id', '!=', rec.id)
                ])
                if val_seq_records:
                    raise UserError(_('You cannot have same sequence!'))

            if rec.sequence > 0 and rec.value_sequence > 0 and rec.sequence == rec.value_sequence:
                    raise UserError(_('You cannot have same sequence!'))

    # @api.onchange('is_carry_forward_refund')
    # def _onchange_carry_forward(self):
    #     warning = {}
    #     if self.is_msic and self.is_carry_forward_refund:
    #         warning = {
    #             'title': _('Warning'),
    #             'message': _('You can not select Is MISC and Is Carry Forward Refund together?')
    #         }
    #         self.is_carry_forward_refund = False
    #     res = {}
    #     if warning:
    #         res['warning'] = warning
    #     return res

    # @api.onchange('is_msic')
    # def _onchange_is_msic(self):
    #     warning = {}
    #     if self.is_msic and self.is_carry_forward_refund:
    #         warning = {
    #             'title': _('Warning'),
    #             'message': _('You can not select Is MISC and Is Carry Forward Refund together?')
    #         }
    #         self.is_msic = False
    #     res = {}
    #     if warning:
    #         res['warning'] = warning
    #     return res


class AccountGST(models.Model):
    _name = 'account.gst'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    print_date = fields.Datetime('Print Date')
    filename = fields.Char('File Name')
    file = fields.Binary('File to Download', readonly=True)
    gst_no = fields.Char('GST No')
    company_name = fields.Char('Name of Business')
    account_gst_line_ids = fields.One2many('account.gst.line', 'account_gst_id', string='GST Lines')
    company_id = fields.Many2one('res.company', 'Company', required=True, 
                                 default=lambda self: self.env['res.company']._company_default_get('account.gst'))


class AccountGSTLine(models.Model):
    _name = 'account.gst.line'

    name = fields.Many2one('gst.mapping', string='Name')
    amount = fields.Float('Amount')
    account_gst_id = fields.Many2one('account.gst', strig='Account GST')
