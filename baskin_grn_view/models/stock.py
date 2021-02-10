# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class StockLocation(models.Model):
    _inherit = "stock.location"
    
    location_mapping_name = fields.Selection([('iglo','Iglo'),
                                              ('batu_caves','Batu Caves'),
                                              ('harus_saujana','Harus Saujana'),
                                              ('hypercold_logistic','Hypercold Logistic'),
                                              ('wlna','WLNA')], string="Location name")
    is_production_location = fields.Boolean('Is Production Location')
    is_outlet_location = fields.Boolean(compute='_get_is_outlet_location', string='Is Outlet Location', store=True)
    outlet_area_manager_id = fields.Many2one('res.users', compute='_get_outlet_area_manager', string="Outlet Area Manager", store=True)
    is_stockist_location = fields.Boolean('Is Stockist Location')

    @api.depends('warehouse_id', 'warehouse_id.outlet_ids')
    @api.multi
    def _get_is_outlet_location(self):
        for record in self:
            location_has_outlet = False
            if record.warehouse_id and record.warehouse_id.outlet_ids:
                location_has_outlet = len(record.warehouse_id.outlet_ids) > 0
            
            record.is_outlet_location = location_has_outlet
    
    @api.depends('warehouse_id', 'warehouse_id.outlet_ids')
    @api.multi
    def _get_outlet_area_manager(self):
        # Note: this method is created with considering that each warehouse only have one outlet confirmed with nicole
        for record in self:
            outlet_area_manager_ids = []
            if record.warehouse_id and record.warehouse_id.outlet_ids:
                for outlet in record.warehouse_id.outlet_ids:
                    if outlet.area_manager:
                        outlet_area_manager_ids.append(outlet.area_manager.id)
            
            if outlet_area_manager_ids and len(outlet_area_manager_ids) == 1:
                record.outlet_area_manager_id = outlet_area_manager_ids[0]


class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    src_location_maping_name = fields.Selection(related='location_id.location_mapping_name', string='Source location mapping name', store=True)
    dest_location_maping_name = fields.Selection(related='location_dest_id.location_mapping_name', string='Destination location mapping name', store=True)


    src_location_is_production = fields.Boolean(related='location_id.is_production_location', string="Source Is Production Location", store=True)
    
    dest_location_is_production = fields.Boolean(related='location_dest_id.is_production_location', string="Destination Is Production Location", store=True)
    src_location_is_outlet = fields.Boolean(related='location_id.is_outlet_location', string="Source Is Outlet Location", store=True)
    
    dest_location_is_outlet = fields.Boolean(related='location_dest_id.is_outlet_location', string="Destination Is Outlet Location", store=True)
    src_location_outlet_area_manager = fields.Many2one('res.users', related='location_id.outlet_area_manager_id', string="Source Outlet Area Manager", store=True)
    
    dest_location_outlet_area_manager = fields.Many2one('res.users', related='location_dest_id.outlet_area_manager_id', string="Destination Outlet Area Manager", store=True)
    
    dest_location_usage = fields.Selection(related='location_dest_id.usage', readonly=True, store=True, string="Destination Location Usage")
    
    pos_order_ids = fields.One2many('pos.order','picking_id', string="POS Order")
    
    src_location_is_loss = fields.Boolean(related='location_id.is_loss_location', string="Source is Loss Location", store=True)
    dest_location_is_loss = fields.Boolean(related='location_dest_id.is_loss_location', string="Destination is Loss Location", store=True)
    
    src_location_is_stockist = fields.Boolean(related='location_id.is_stockist_location', string="Source is Stockist", store=True)
    dest_location_is_stockist = fields.Boolean(related='location_dest_id.is_stockist_location', string="Destination is Stockist", store=True)
    # FIXME: this field is referencing to is_mega_scoop field which is declared in baskin_partner_id module, but this module isn't referencing to it
    is_mega_scoop_picking = fields.Boolean(related='partner_id.is_mega_scoop', string='Is Mega Scoop', store=True)
