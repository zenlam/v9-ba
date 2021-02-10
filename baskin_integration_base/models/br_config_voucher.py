# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class Voucher(models.Model):
    _inherit = "br.config.voucher"

    batch_number = fields.Char(string='Voucher Batch No.')
    member_id = fields.Many2one('third.party.member', string='Member')
    member_code = fields.Char(related='member_id.code', string='Member Code',
                              store=True)
    shared_voucher = fields.Boolean(string='Voucher Being Shared?',
                                    default=False)

    @api.model
    def check_promotion_member(self, voucher_validation_code):
        """ Handle the logic of Member Voucher Code. Inherit this function """
        return []

    @api.multi
    def update_coupon_sync(self):
        """ Handle the logic of updating the coupon code of third party.
        Inherit this function """
        return False

    @api.model
    def get_membership_id(self):
        """
        Cron job to fill in missing member id in coupon code
        """

        return
