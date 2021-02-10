# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import ValidationError
from collections import OrderedDict


class Promotion(models.Model):
    _inherit = "br.bundle.promotion"

    third_party_id = fields.Many2one(
        'third.party', string='Third Party', required=True)
    sync_id = fields.Char(
        string='Sync ID', readonly=1, copy=False,
        help='The record ID of third party database. The value is returned '
             'from the third party after Odoo syncing the data.')
    create_code_api = fields.Boolean(related='third_party_id.create_code_api')
    sync_promotion_data = fields.Boolean(
        related='third_party_id.sync_promotion_data')
    default_number_of_digit = fields.Integer(string='Number of Digit')
    default_number_of_alphabet = fields.Integer(string='Number of Alphabet')
    default_remarks = fields.Char(string='Code Remark')
    last_sync_info = fields.Char(string='Last Sync Information')

    @api.multi
    def sync_data(self):
        """
        Sync the promotion data to the Third Party
        """
        return

    @api.multi
    def suspend(self):
        """
        Suspend the promotion from the Third Party
        """
        return

    @api.constrains('third_party_id', 'is_voucher')
    def _check_third_party_voucher(self):
        """ Raise error when a non BR third party does not implement use code
        """
        if self.third_party_id and not self.third_party_id.is_baskin \
                and not self.is_voucher:
            raise ValidationError(_("Third Party Discount should implement "
                                    "voucher."))


class ThirdPartyPromotionSyncLog(models.Model):
    _name = 'third.party.promotion.sync.log'
    _description = 'Log file that keep track the promotion master data ' \
                   'syncing.'
    _order = 'sync_datetime desc'

    sync_datetime = fields.Datetime(string='Sync Time')
    sync_info = fields.Html(string='Sync Information')
    sync_status = fields.Selection([('success', 'Success'), ('fail', 'Fail'),
                                    ('unreachable', 'Unreachable')],
                                   string='Sync Status', default='unreachable')
    rec_id = fields.Char(string='Discount ID')
    rec_name = fields.Char(string='Discount Name')
    third_party_id = fields.Many2one('third.party', string='Third Party')
    third_party_code = fields.Char(related='third_party_id.code',
                                   string='Third Party Name',
                                   store=True)
