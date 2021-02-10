# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class Menu(models.Model):
    _inherit = "product.product"

    third_party_sync_ids = fields.One2many(
        'third.party.menu.sync',
        'menu_id',
        string='Third Party Syncing')

    @api.multi
    def sync_data_all(self):
        """
        Sync the outlet data to all third party
        """
        for rec in self:
            for sync in rec.third_party_sync_ids:
                sync.sync_data()
