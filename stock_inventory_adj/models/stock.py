# -*- coding: utf-8 -*-

from openerp import fields, models


class stock_warehouse(models.Model):
    _inherit = 'stock.warehouse'

    gain_src_location_id = fields.Many2one('stock.location', string='Gain Source Location')
    gain_dest_location_id = fields.Many2one('stock.location', string='Gain Destination Location')

    loss_src_location_id = fields.Many2one('stock.location', string='Loss Source Location')
    loss_dest_location_id = fields.Many2one('stock.location', string='Loss Destination Location')

    damage_src_location_id = fields.Many2one('stock.location', string='Damage Source Location')
    damage_dest_location_id = fields.Many2one('stock.location', string='Damage Destination Location')

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    validated_by = fields.Many2one('res.users', string="Validated By")

    def do_transfer(self, cr, uid, ids, context=None):
        for pick in self.browse(cr, uid, ids, context=context):
            pick.validated_by = pick.env.user.id
        return super(StockPicking, pick).do_transfer()
