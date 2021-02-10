# -*- coding: utf-8 -*-

from openerp import tools
from openerp import models, fields, api
from openerp.addons.procurement import procurement
import openerp.addons.decimal_precision as dp
from openerp.tools.float_utils import float_compare, float_round
from openerp.tools.translate import _

class stock_move_cake_ordering(models.Model):
    _name = "stock.move.cake.ordering"
    _description = "Stock Move Cake Ordering"
    _auto = False

    def _get_string_qty_information(self):
        uom_obj = self.env['product.uom']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for move in self:
            if move.state in ('draft', 'done', 'cancel') or move.location_id.usage != 'internal':
                move.string_availability_info = ''  # 'not applicable' or 'n/a' could work too
                continue
            total_available = min(move.product_qty, move.reserved_availability + move.availability)
            total_available = uom_obj._compute_qty_obj(move.product_id.uom_id, total_available, move.product_uom, round=False)
            total_available = float_round(total_available, precision_digits=precision)
            info = str(total_available)
            #look in the settings if we need to display the UoM name or not
            if self.env['res.users'].has_group('product.group_uom'):
                info += ' ' + move.product_uom.name
            if move.reserved_availability:
                if move.reserved_availability != total_available:
                    #some of the available quantity is assigned and some are available but not reserved
                    reserved_available = uom_obj._compute_qty_obj(move.product_id.uom_id, move.reserved_availability, move.product_uom, round=False)
                    reserved_available = float_round(reserved_available, precision_digits=precision)
                    info += _(' (%s reserved)') % str(reserved_available)
                else:
                    #all available quantity is assigned
                    info += _(' (reserved)')
            move.string_availability_info = info
    
    def _get_reserved_availability(self):
        for move in self:
            move.reserved_availability = sum([quant.qty for quant in move.reserved_quant_ids])
            
    def _get_product_availability(self):
        quant_obj = self.env['stock.quant']
        for move in self:
            if move.state == 'done':
                move.availability = move.product_qty
            else:
                sublocation_ids = self.env['stock.location'].search([('id', 'child_of', [move.location_id.id])])
                quant_ids = quant_obj.search([('location_id', 'in', sublocation_ids.ids), ('product_id', '=', move.product_id.id), ('reservation_id', '=', False)])
                availability = 0
                for quant in quant_ids:
                    availability += quant.qty
                move.availability = min(move.product_qty, availability)
    
    id = fields.Integer('Move Id')
    origin = fields.Char("Source Document")
    create_date = fields.Datetime('Creation Date', readonly=True, select=True)
    product_uom = fields.Many2one('product.uom', 'Unit of Measure', readonly=True)
    product_uom_qty = fields.Float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
            readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, select=True)
    remarks = fields.Text('Remarks')
    location_id = fields.Many2one('stock.location', 'Source Location', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Destination Address')
    state = fields.Selection([('draft', 'New'),
                               ('cancel', 'Cancelled'),
                               ('waiting', 'Waiting Another Move'),
                               ('confirmed', 'Waiting Availability'),
                               ('assigned', 'Available'),
                               ('done', 'Done'),
                               ('processed', 'Processed'), 
                               ('transit', 'Transit'), 
                               ('undelivered', 'Undelivered')
                               ], 'Status', readonly=True)
    purchase_line_id = fields.Many2one('purchase.order.line',
            'Purchase Order Line', select=True,
            readonly=True)
    from_cake_location = fields.Boolean('From Cake location')
    date_expected = fields.Datetime('Expected Date', readonly=True)
    string_availability_info = fields.Text(compute='_get_string_qty_information', string='Availability', readonly=True, help='Show various information on stock availability for this move')
    reason_of_reverse = fields.Many2one('reverse.transfer.reason.category', string="Reason of Reverse")
    move_dest_id = fields.Many2one('stock.move', 'Destination Move')
    date = fields.Datetime('Date', readonly=True)
    procure_method = fields.Selection([('make_to_stock', 'Default: Take From Stock'), ('make_to_order', 'Advanced: Apply Procurement Rules')], 'Supply Method', readonly=True, 
                                           help="""By default, the system will take from the stock in the source location and passively wait for availability. The other possibility allows you to directly create a procurement on the source location (and thus ignore its current stock) to gather products. If we want to chain moves and have this one to wait for the previous, this second option should be chosen.""")
    group_id = fields.Many2one('procurement.group', 'Procurement Group', readonly=True)
    name = fields.Char('Description', readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', 'Picking Type', readonly=True)
    picking_id = fields.Many2one('stock.picking', 'Transfer Reference')
    picking_partner_id = fields.Many2one(related='picking_id.partner_id', string='Transfer Destination Address')
    quant_ids = fields.Many2many('stock.quant', 'stock_quant_move_rel', 'move_id', 'quant_id', 'Moved Quants')
    location_dest_id = fields.Many2one('stock.location', 'Destination Location', readonly=True,
                                            help="Location where the system will stock the finished products.")
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    priority = fields.Selection(procurement.PROCUREMENT_PRIORITIES, 'Priority')
    product_qty = fields.Float('Quantity')
    reserved_availability = fields.Float(compute='_get_reserved_availability', string='Quantity Reserved', readonly=True, help='Quantity that has already been reserved for this move')
    reserved_quant_ids = fields.One2many('stock.quant', 'reservation_id', 'Reserved quants')
    availability = fields.Float(compute='_get_product_availability', type='float', string='Forecasted Quantity', readonly=True, help='Quantity in stock that can still be reserved for this move')
    
    def init(self, cr):
        print "--------> init of cake ordering--------"
        tools.drop_view_if_exists(cr, 'stock_move_cake_ordering')
        cr.execute("""
        CREATE or REPLACE VIEW stock_move_cake_ordering as (
        
            select
                
                id,
                origin,
                create_date,
                product_uom,
                product_uom_qty,
                company_id,
                remarks,
                location_id,
                partner_id,
                state,
                purchase_line_id,
                from_cake_location,
                date_expected,
--                string_availability_info,
                reason_of_reverse,
                move_dest_id,
                date,
                procure_method,
                group_id,
                name,
                picking_type_id,
                
                picking_id,
                location_dest_id,
                product_id,
                priority,
                product_qty
            
            from stock_move
            
            where 
                from_cake_location = True
            
        )""")
