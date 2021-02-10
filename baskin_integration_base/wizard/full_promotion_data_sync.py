# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class FullPromotionDataSync(models.TransientModel):
    _name = "full.promotion.data.sync"
    _description = 'This wizard will sync the latest information of ' \
                   'promotions to every third party.'

    @api.multi
    def action_sync(self):
        """ This function will sync the promotions data to all third party """
        promotion_ids = self.env['br.bundle.promotion'].search([
            ('sync_promotion_data', '=', True)])
        promotion_ids.sync_data()