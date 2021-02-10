# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class PromotionVoucherGen(models.TransientModel):
    _inherit = "br.promotion.voucher.gen"

    batch_number = fields.Char(string='Voucher Batch No.')

    def prepare_voucher_vals(self, sequence):
        """ update the batch number of voucher """
        vals = super(PromotionVoucherGen, self).prepare_voucher_vals(sequence)
        vals.update({
            'batch_number': self.batch_number,
        })
        return vals
