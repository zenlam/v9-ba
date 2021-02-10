# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class FullOutletDataSync(models.TransientModel):
    _name = "full.outlet.data.sync"
    _description = "This wizard will sync the latest information of outlets " \
                   "to every third party."

    @api.multi
    def action_sync(self):
        """ This function will sync the outlets data to all third party """
        outlet_sync_ids = self.env['third.party.outlet.sync'].search([])
        outlet_sync_ids.sync_data()