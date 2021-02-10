__author__ = 'trananhdung'

from openerp import models, fields, api, _

class hanel_pos_terminal(models.Model):
    _name = 'hanel.pos.terminal'

    name = fields.Char(string='Name')
    file = fields.Binary(string="File")
    link = fields.Char(string='Download Link')
    version = fields.Char(string="Version")
    sequence = fields.Integer(string="Sequence")    
    group = fields.Selection([
            ('terminal', 'POS Installer')
        ], 'Group')
    _order = 'sequence desc'

hanel_pos_terminal()
