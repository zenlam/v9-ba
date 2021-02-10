# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.exceptions import UserError


class res_company(models.Model):
    _inherit = 'res.company'

    sequence_number_setting = fields.Many2one('ir.sequence', string="Partner Sequence Number", required=True)
    is_mega_scoop = fields.Boolean('Is Mega Scoop', help="If this checkbox is ticked, when print Invoices/CN, it will show label 'Tax Invoice'.")
    is_golden_scoop = fields.Boolean('Is Golden Scoop', help="If this checkbox is ticked, when print Invoices/CN, it will show label 'Invoice'.")

    @api.constrains('is_golden_scoop', 'is_mega_scoop')
    def check_company(self):
        for record in self:
            if record.is_golden_scoop and record.is_mega_scoop:
                raise UserError(_("A company can't be Mega Scoop and Golden Scoop at the same time."))


class res_partner(models.Model):
    _inherit = "res.partner"

    sequence_no = fields.Char('Sequence Number', default=lambda self: self.next_seq_cus(), readonly=True)
    business_registration_no = fields.Char('Business Registration No')
    is_mega_scoop = fields.Boolean('Is Mega Scoop')

    @api.model
    def create(self, vals):
        company = self.env['res.company'].browse(self.env.user.company_id.id)
        if not company.sequence_number_setting:
            vals['sequence_no'] = ""
        else:
            seq = self.env['ir.sequence'].search([('id', '=', company.sequence_number_setting.id)])
            vals['sequence_no'] = seq.next_by_id()
        return super(res_partner, self).create(vals)

    def next_seq_cus(self):
        company = self.env['res.company'].browse(self.env.user.company_id.id)
        if not company.sequence_number_setting:
            next_seq = ""
        else:
            seq = self.env['ir.sequence'].search([('id', '=', company.sequence_number_setting.id)])
            next_seq = seq.get_next_char(seq.number_next_actual)
        return next_seq

    _sql_constraints = [
        ('sequence_no_unique', 'unique(sequence_no)', 'sequence already exists!')
    ]

    class ResPartnerBank(models.Model):
        _inherit = "res.partner.bank"

        swift_code = fields.Char('Swift Code')