# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import ValidationError, UserError


class OutletFacility(models.Model):
    _name = "outlet.facility"
    _description = 'Facility provided in an outlet'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    outlet_ids = fields.Many2many('br_multi_outlet.outlet',
                                  'outlet_outlet_facility_rel',
                                  'facility_id',
                                  'outlet_id',
                                  string='Outlets')
    outlet_count = fields.Integer(compute='_outlet_count',
                                  string='Outlet Count')

    _sql_constraints = [
        ('facility_name_uniq',
         'unique(name)',
         _('Outlet Facility Name should be Unique!')),
    ]

    def _outlet_count(self):
        """ compute the total outlet having current facility """
        for record in self:
            record.outlet_count = len(record.outlet_ids)

    @api.multi
    def toggle_active(self):
        """ Function to handle activate and deactivate logic """
        for record in self:
            if record.active and record.outlet_ids:
                outlet_name = '\n'.join([outlet.name
                                         for outlet in record.outlet_ids])
                raise UserError(_('Kindly remove this facility from following '
                                  'outlets then deactivate this facility: '
                                  '\n%s') % outlet_name)
            record.active = not record.active
