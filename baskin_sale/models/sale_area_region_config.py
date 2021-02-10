# -*- coding: utf-8 -*-
from openerp import api, fields, models, _


class CustomerArea(models.Model):
    _name = "customer.area"

    name = fields.Char('Area', required=True)
    state_id = fields.Many2one('res.country.state', string='State', required=True)


class CustomerRegion(models.Model):
    _name = "customer.region"

    name = fields.Char('Region', required=True)


class CountryState(models.Model):
    _inherit = 'res.country.state'

    region_id = fields.Many2one('customer.region', string='Region', required=True)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    area_id = fields.Many2one('customer.area', string='Area', required=True)


