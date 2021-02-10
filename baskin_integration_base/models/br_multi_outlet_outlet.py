# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class Outlet(models.Model):
    _inherit = "br_multi_outlet.outlet"

    third_party_sync_ids = fields.One2many(
        'third.party.outlet.sync',
        'outlet_id',
        string='Third Party Syncing')
    outlet_coord = fields.Char(string='Outlet Coordinates')
    outlet_weekday_opening = fields.Char(string='Weekday Opening Hours',
                                         help='Time format: 090000 - 220000')
    outlet_weekend_opening = fields.Char(string='Weekend Opening Hours',
                                         help='Time format: 090000 - 220000')
    outlet_holiday_opening = fields.Char(string='Holiday Opening Hours',
                                         help='Time format: 090000 - 220000')
    facility_ids = fields.Many2many('outlet.facility',
                                    'outlet_outlet_facility_rel',
                                    'outlet_id',
                                    'facility_id',
                                    string='Facilities')

    @api.multi
    def sync_data_all(self):
        """
        Sync the outlet data to all third party
        """
        for rec in self:
            for sync in rec.third_party_sync_ids:
                sync.sync_data()
