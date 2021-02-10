# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
import random
import string
import re
import datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT


class BrPromotionVoucherGen(models.TransientModel):
    _name = "br.promotion.voucher.gen"
    _description = "Promotion Voucher Gen"

    def gen_random_code(self, promotion_code, number_of_digit, number_of_alphabet):
        code = ''
        if promotion_code:
            code += promotion_code + '-'
        if number_of_alphabet:
            code += ''.join(random.choice(re.sub(r'[IOLRM]','', string.ascii_uppercase)) for x in range(number_of_alphabet))
        if number_of_digit:
            code += ''.join(random.choice('123456789') for x in range(number_of_digit))
        return code

    @api.multi
    @api.depends('promotion_id', 'number_of_digit', 'number_of_alphabet')
    def compute_code(self):
        for r in self:
            self.code = self.gen_random_code(False, r.number_of_digit, r.number_of_alphabet)

    promotion_id = fields.Many2one('br.bundle.promotion', string='Promotion', ondelete='restrict')
    partner_id = fields.Many2one('res.partner', string='Customer')
    qty = fields.Integer('Quantity', default=100, required=1)
    start_date = fields.Date(string='Start Date', required=1)
    end_date = fields.Date(string='End Date')
    number_of_digit = fields.Integer('Number of Digit', default=3, required=1)
    number_of_alphabet = fields.Integer('Number of Alphabet', default=1, required=1)
    code = fields.Char('Code', compute=compute_code)
    use_validation_code = fields.Boolean(string="Use validation code", default=True)
    remarks = fields.Char(string='Remarks', required=1)
    approval_no = fields.Char(string='Approval No.', required=1)

    @api.multi
    def gen(self):
        """ Call function to generate voucher and close the wizard """
        self.gen_base()
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def gen_base(self):
        """ Function to generate voucher and return the created voucher ids
        :return: voucher_ids
        """
        voucher_ids = []
        for r in self:
            sequence = r.get_latest_voucher_sequence(r.qty)
            for i in xrange(0, r.qty):
                sequence += 1
                # prepare the vals dictionary to generate voucher
                vals = r.prepare_voucher_vals(sequence)
                voucher = self.env['br.config.voucher'].create(vals)
                voucher_ids.append(voucher.id)
        return voucher_ids

    @api.multi
    def get_latest_voucher_sequence(self, qty):
        """ Function to get the latest voucher sequence and perform increment
        """
        self.ensure_one()
        last_voucher_sequence = self.promotion_id.last_voucher_sequence
        # reserved the last_voucher_sequence until the number of the
        # last_voucher_sequence + qty for this batch
        self.promotion_id.write({
            'last_voucher_sequence': last_voucher_sequence + qty
        })
        # commit the update and release the row level lock of the promotion
        self.env.cr.commit()
        return last_voucher_sequence

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.remarks = self.partner_id.display_name

    def prepare_voucher_vals(self, sequence):
        """ Prepare the voucher values dictionary
        """
        return {
            'promotion_id': self.promotion_id.id,
            'partner_id': self.partner_id and self.partner_id.id or False,
            'start_date': self.start_date,
            'end_date': self.end_date or False,
            'status': 'available',
            'validation_code': self.gen_random_code(False, self.number_of_digit, self.number_of_alphabet) if self.use_validation_code else False,
            'voucher_code': "%s%s"%(self.promotion_id.code, str(sequence)),
            'sequence': sequence,
            'remarks': self.remarks,
            'approval_no': self.approval_no
        }


class BrPromotionVoucherEndDate(models.TransientModel):
    _name = "br.promotion.voucher.enddate"
    _description = "Promotion Voucher End Date"

    end_date = fields.Date(string='End Date')
    start_code = fields.Integer(string="Start code")
    end_code = fields.Integer(string="End code")
    promotion_id = fields.Many2one('br.bundle.promotion', string='Promotion', ondelete='restrict')
    partner_id = fields.Many2one('res.partner', string='Customer')
    remarks = fields.Char(string='Remarks')
    approval_no = fields.Char(string='Approval No.')

    @api.multi
    def update_enddate(self):
        for r in self:
            for line in r.promotion_id.voucher_ids:
                # num_code = int(line.voucher_code.rsplit('-', 1)[1])
                num_code = int(line.sequence)
                start_code = r.start_code or 0
                end_code = r.end_code or -1
                if ((end_code < 0) and num_code >= start_code) or (end_code > 0 and start_code <= num_code <= end_code):
                    vals = {}
                    if r.end_date:
                        if line.status != 'redeemed':
                            vals.update(end_date=r.end_date)
                            if r.end_date >= datetime.datetime.strftime(datetime.date.today(), DEFAULT_SERVER_DATE_FORMAT):
                                line.status = 'available'
                    if r.partner_id.id:
                        vals.update(partner_id=r.partner_id.id)
                    if r.remarks:
                        vals.update(remarks=r.remarks)
                    if r.approval_no:
                        vals.update(approval_no=r.approval_no)
                    if vals:
                        line.write(vals)
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def delete_voucher(self):
        for r in self:
            for line in r.promotion_id.voucher_ids:
                if line.status not in ('redeemed', 'expired'):
                    # num_code = int(line.voucher_code.rsplit('-', 1)[1])
                    num_code = int(line.sequence)
                    start_code = r.start_code or 0
                    end_code = r.end_code or -1
                    if ((end_code < 0) and num_code >= start_code) or \
                            (end_code > 0 and start_code <= num_code <= end_code):
                        line.unlink()
        return {'type': 'ir.actions.act_window_close'}

BrPromotionVoucherEndDate()
