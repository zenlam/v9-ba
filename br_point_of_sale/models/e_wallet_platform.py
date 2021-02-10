# -*- coding: utf-8 -*-

from openerp import models, fields, api, _


class EWalletPlatform(models.Model):
    _name = 'e.wallet.platform'
    _description = 'E Wallet Platform'

    name = fields.Char(name='Platform Name', required=True)
    cimb_machine_code = fields.Char(name='CIMB Machine Code')
