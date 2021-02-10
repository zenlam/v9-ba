# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class OutletMobileAppsStatus(models.Model):
    _name = "outlet.mobile.app.status"
    _description = "Outlet Status in Mobile Apps"

    name = fields.Char(string='Status Name')
    allow_receive_order = fields.Boolean(string='Receive Order in Mobile Apps',
                                         default=False)
    visible_in_apps = fields.Boolean(string='Visible in Mobile Apps',
                                     default=False)

    _sql_constraints = [
        ('status_name_uniq',
         'unique(name)',
         _('App Status Name should be Unique!')),
    ]
