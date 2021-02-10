# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class Outlet(models.Model):
    _inherit = "br_multi_outlet.outlet"

    mobile_status = fields.Many2one('outlet.mobile.app.status',
                                    string='Mobile Apps Status')
    visible_in_apps = fields.Boolean(related='mobile_status.visible_in_apps',
                                     string='Visible in Mobile Apps')
