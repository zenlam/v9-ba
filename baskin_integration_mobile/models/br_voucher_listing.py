# -*- coding: utf-8 -*-

from openerp import models, fields, api, tools
from openerp import models, fields, api, SUPERUSER_ID, _


class br_voucher_listing(models.Model):
    _inherit = 'br.voucher.listing'

    third_party_id = fields.Char(string='Third Party', readonly=True)
    free_deal = fields.Boolean(string='Free Coupon', default=False,
                               readonly=True)
    flexible_end_date = fields.Boolean(string='Flexible End Date',
                                       default=False, readonly=True)
    validity_days = fields.Integer(string='Validity (in Days)', readonly=True)
    member_id = fields.Char(string='Member', readonly=True)
    shared_voucher = fields.Boolean(string='Voucher Being Shared',
                                    readonly=True)

    def select(self):
        old_select = super(br_voucher_listing, self).select()
        new_select = old_select + (
                    """
                    ,
                    tp.name AS third_party_id,
                    bbp.free_deal AS free_deal,
                    bbp.flexible_end_date AS flexible_end_date,
                    bbp.validity_days AS validity_days,
                    tpm.code AS member_id,
                    bcv.shared_voucher AS shared_voucher
                    """
        )
        return new_select

    def from_query(self):
        old_from = super(br_voucher_listing, self).from_query()
        new_from = old_from + ("""
                    LEFT JOIN third_party tp
                    ON bbp.third_party_id = tp.id
                    LEFT JOIN third_party_member tpm
                    ON bcv.member_id = tpm.id
                    """
        )
        return new_from


br_voucher_listing()
