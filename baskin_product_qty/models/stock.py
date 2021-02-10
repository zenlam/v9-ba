# -*- coding: utf-8 -*-

from openerp import api, fields, models


class Product(models.Model):
    _inherit = 'product.product'

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        if self.env.context.get('from_category'):
            category_ids = self.env.context['from_category']
            if category_ids and category_ids[0] and category_ids[0][2]:
                products = self.search([('categ_id', 'child_of', category_ids[0][2])], order='id')
                domain += [('id', 'in', products.ids)]
        return super(Product, self).name_search(name=name, args=args + domain, operator=operator, limit=limit)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        if self.env.context.get('from_warehouse'):
            warehouse_ids = self.env.context['from_warehouse']
            if warehouse_ids and warehouse_ids[0] and warehouse_ids[0][2]:
                warehouses = self.env['stock.warehouse'].browse(warehouse_ids[0][2])
                location_ids = warehouses.mapped('view_location_id').ids
                locations = self.search([('id', 'child_of', location_ids)], order='id')
                domain += [('id', 'in', locations.ids)]
        return super(StockLocation, self).name_search(name=name, args=args + domain, operator=operator, limit=limit)


class StockProductQty(models.Model):
    _name = 'stock.product.qty'

    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('product.uom', string='UoM')
    available_qty = fields.Float('Available')
    processed_qty = fields.Float('Processed')
    transit_qty = fields.Float('Transit')
    total_reverse = fields.Float('Total Reserve')
    draft_qty = fields.Float('New')
    waiting_another_move = fields.Float('Waiting Another Move')
    waiting_availablity = fields.Float('Waiting Availability')
    partial_available_qty = fields.Float('Partial Available')
    force_availability_qty = fields.Float('Force Availability')
    shortage_qty = fields.Float('Shortage')
    no_action = fields.Float('No Action')
    free_reserve = fields.Float('Free for Reserve')
    qty_on_hand = fields.Float('Qty on Hand')
    qty_needed = fields.Float('Total Qty Required')
    picking_ids = fields.Many2many(
                    'stock.picking',
                    'stock_picking_product_qty_rel',
                    'stock_product_id',
                    'picking_id',
                    string='Pickings')
    distribution_uom_id = fields.Many2one('product.uom', string='Product UoM')
    uom_ids = fields.Many2many(
                'product.uom',
                'stoc_product_uom_rel',
                'stock_uom_id',
                'uom_id',
                string='UoM')

    back_available_qty = fields.Float('Available')
    back_processed_qty = fields.Float('Processed')
    back_transit_qty = fields.Float('Transit')
    back_total_reverse = fields.Float('Total Reserve')
    back_draft_qty = fields.Float('New')
    back_waiting_another_move = fields.Float('Waiting Another Move')
    back_waiting_availablity = fields.Float('Waiting Availability')
    back_partial_available_qty = fields.Float('Partial Available')
    back_force_availability_qty = fields.Float('Force Availability')
    back_shortage_qty = fields.Float('Shortage')
    back_qty_needed = fields.Float('Total Qty Required')
    back_no_action = fields.Float('No Action')
    back_free_reserve = fields.Float('Free for Reserve')
    back_qty_on_hand = fields.Float('Qty on Hand')

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        ProductUoM = self.env['product.uom']
        if self.uom_id:
            available_qty = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.available_qty, self.uom_id)
            processed_qty = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.processed_qty, self.uom_id)
            transit_qty = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.transit_qty, self.uom_id)
            total_reverse = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.total_reverse, self.uom_id)
            draft_qty = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.draft_qty, self.uom_id)
            waiting_another_move = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.waiting_another_move, self.uom_id)
            waiting_availablity = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.waiting_availablity, self.uom_id)
            partial_available_qty = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.partial_available_qty, self.uom_id)
            no_action = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.no_action, self.uom_id)
            free_reserve = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.free_reserve, self.uom_id)
            qty_on_hand = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.qty_on_hand, self.uom_id)
            force_availability_qty = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.force_availability_qty, self.uom_id)
            shortage_qty = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.shortage_qty, self.uom_id)
            qty_needed = ProductUoM._compute_qty_obj(self.distribution_uom_id, self.qty_needed, self.uom_id)

            self.available_qty = available_qty
            self.processed_qty = processed_qty
            self.transit_qty = transit_qty
            self.total_reverse = total_reverse
            self.draft_qty = draft_qty
            self.waiting_another_move = waiting_another_move
            self.waiting_availablity = waiting_availablity
            self.partial_available_qty = partial_available_qty
            self.force_availability_qty = force_availability_qty
            self.shortage_qty = shortage_qty
            self.no_action = no_action
            self.free_reserve = free_reserve
            self.qty_on_hand = qty_on_hand
            self.qty_needed = qty_needed

            self.distribution_uom_id = self.uom_id

            self.back_available_qty = available_qty
            self.back_processed_qty = processed_qty
            self.back_transit_qty = transit_qty
            self.back_total_reverse = total_reverse
            self.back_draft_qty = draft_qty
            self.back_waiting_another_move = waiting_another_move
            self.back_waiting_availablity = waiting_availablity
            self.back_partial_available_qty = partial_available_qty
            self.back_force_availability_qty = force_availability_qty
            self.back_shortage_qty = shortage_qty
            self.back_qty_needed = qty_needed
            self.back_no_action = no_action
            self.back_free_reserve = free_reserve
            self.back_qty_on_hand = qty_on_hand

    @api.multi
    def write(self, vals):
        if vals.get('back_available_qty'):
            vals['available_qty'] = vals['back_available_qty']
        if vals.get('back_processed_qty'):
            vals['processed_qty'] = vals['back_processed_qty']
        if vals.get('back_transit_qty'):
            vals['transit_qty'] = vals['back_transit_qty']
        if vals.get('back_total_reverse'):
            vals['total_reverse'] = vals['back_total_reverse']
        if vals.get('back_draft_qty'):
            vals['draft_qty'] = vals['back_draft_qty']

        if vals.get('back_waiting_another_move'):
            vals['waiting_another_move'] = vals['back_waiting_another_move']
        if vals.get('back_waiting_availablity'):
            vals['waiting_availablity'] = vals['back_waiting_availablity']
        if vals.get('back_partial_available_qty'):
            vals['partial_available_qty'] = vals['back_partial_available_qty']
        if vals.get('back_force_availability_qty'):
            vals['force_availability_qty'] = vals['back_force_availability_qty']
        if vals.get('back_shortage_qty'):
            vals['shortage_qty'] = vals['back_shortage_qty']
        if vals.get('back_qty_needed'):
            vals['qty_needed'] = vals['back_qty_needed']

        if vals.get('back_no_action'):
            vals['no_action'] = vals['back_no_action']

        if vals.get('back_free_reserve'):
            vals['free_reserve'] = vals['back_free_reserve']

        if vals.get('back_qty_on_hand'):
            vals['qty_on_hand'] = vals['back_qty_on_hand']

        return super(StockProductQty, self).write(vals)

    @api.multi
    def show_picking(self):
        self.ensure_one()
        # view = self.env.ref('br_stock_request.view_picking_transfer_tree')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Qty on Hand Check',
            'view_type': 'form',
            'view_mode': 'tree,kanban,form,calendar',
            'view_id': False,
            'res_model': 'stock.picking',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {'create': False},
        }
        return True

    @api.model
    def auto_unlink(self):
        all_records = self.env['stock.product.qty'].search([])
        all_records.unlink()

