from openerp import models, fields, api, _, SUPERUSER_ID
from openerp.exceptions import UserError, ValidationError
from openerp.tools.float_utils import float_compare, float_round
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_REPEATABLE_READ


class br_stock_quant(models.Model):
    _inherit = "stock.quant"

    @api.multi
    @api.depends('qty', 'uom_l2_id')
    def _compute_qty_uom_2(self):
        this = self[0]
        if this.uom_l2_id:
            uom_obj = self.env['product.uom']
            qty = uom_obj._compute_qty_obj(this.product_id.product_tmpl_id.uom_id, this.qty, this.uom_l2_id, True, 'HALF-UP')
            this.qty_l2 = qty

    @api.multi
    @api.depends('qty', 'uom_l3_id')
    def _compute_qty_uom_3(self):
        this = self[0]
        if this.uom_l3_id:
            uom_obj = self.env['product.uom']
            qty = uom_obj._compute_qty_obj(this.product_id.product_tmpl_id.uom_id, this.qty, this.uom_l3_id, True, 'HALF-UP')
            this.qty_l3 = qty

    @api.multi
    @api.depends('qty', 'uom_l4_id')
    def _compute_qty_uom_4(self):
        this = self[0]
        if this.uom_l4_id:
            uom_obj = this.env['product.uom']
            qty = uom_obj._compute_qty_obj(this.product_id.product_tmpl_id.uom_id, this.qty, this.uom_l4_id, True, 'HALF-UP')
            this.qty_l4 = qty

    vendor_id = fields.Many2one('res.partner', string="Supplier")
    uom_l2_id = fields.Many2one('product.uom', string="UOM level 2")
    uom_l3_id = fields.Many2one('product.uom', string="UOM level 3")
    uom_l4_id = fields.Many2one('product.uom', string="UOM level 4")
    qty_l2 = fields.Float(string="Quantity level 2", compute='_compute_qty_uom_2', store=True)
    qty_l3 = fields.Float(string="Quantity level 3", compute='_compute_qty_uom_3', store=True)
    qty_l4 = fields.Float(string="Quantity level 4", compute='_compute_qty_uom_4', store=True)

    @api.model
    def _quant_create(self, qty, move, lot_id=False, owner_id=False, src_package_id=False, dest_package_id=False,
                      force_location_from=False, force_location_to=False):
        """Override function: add to stock quant field supplier"""
        result = super(br_stock_quant, self)._quant_create(qty, move, lot_id, owner_id, src_package_id, dest_package_id, force_location_from, force_location_to)
        # Find negative quants that created by this quant
        negative_quant = self.search([('negative_move_id', '=', move.id), ('product_id', '=', move.product_id.id), ('lot_id', '=', lot_id)])
        if move.purchase_line_id:
            # Move is created from Purchase order
            partner_id = move.purchase_line_id.order_id.partner_id.id if move.purchase_line_id.order_id.partner_id else False
        elif move.inventory_line_id:
            # Move is created from Inventory Adjustment
            partner_id = move.inventory_line_id.br_supplier_id.id if move.inventory_line_id.br_supplier_id else False
        else:
            partner_id = self.env.context.get('quant_partner_id', False)
        if partner_id:
            uom_l2_id = uom_l3_id = uom_l4_id = False
            result.vendor_id = partner_id
            product_tmpl_id = move.product_id.product_tmpl_id.id
            ls_supplier_info = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product_tmpl_id), ('name', '=', partner_id)])
            ls_uoms = []
            for supplier_info in ls_supplier_info:
                ls_uoms.extend(supplier_info.uom_ids)
            for uom in ls_uoms:
                level = uom.level_uom
                if level == 'level2':
                    uom_l2_id = uom.id
                if level == 'level3':
                    uom_l3_id = uom.id
                if level == 'level4':
                    uom_l4_id = uom.id
            result.write({'vendor_id': partner_id,
                          'uom_l2_id': uom_l2_id,
                          'uom_l3_id': uom_l3_id,
                          'uom_l4_id': uom_l4_id})
            # bg update uom for negative_quant
            for negative in negative_quant:
                negative.write({
                    'vendor_id': partner_id,
                    'uom_l2_id': uom_l2_id,
                    'uom_l3_id': uom_l3_id,
                    'uom_l4_id': uom_l4_id,
                })
                # end update uom for negative_quant

        return result

    def _quant_split(self, cr, uid, quant, qty, context=None):
        context = context or {}
        rounding = quant.product_id.uom_id.rounding
        # if quant <= qty in abs, take it entirely
        if float_compare(abs(quant.qty), abs(qty), precision_rounding=rounding) <= 0:
            return False
        qty_round = float_round(qty, precision_rounding=rounding)
        new_qty_round = float_round(quant.qty - qty, precision_rounding=rounding)
        # Fetch the history_ids manually as it will not do a join with the stock moves then (=> a lot faster)
        cr.execute("""SELECT move_id FROM stock_quant_move_rel WHERE quant_id = %s""", (quant.id,))
        res = cr.fetchall()
        # update uom,qty l2-l4
        if not quant.lot_id:
            new_quant = self.copy(cr, SUPERUSER_ID, quant.id, default={
                'qty': new_qty_round,
                'history_ids': [(4, x[0]) for x in res]
            }, context=context)
            self.write(cr, SUPERUSER_ID, quant.id, {'qty': qty_round}, context=context)
        else:
            partner_id = quant.vendor_id
            uom_l2_id = uom_l3_id = uom_l4_id = False
            if partner_id:
                product_tmpl_id = quant.product_id.product_tmpl_id.id
                ls_supplier_info = self.pool['product.supplierinfo'].search(cr, uid, [('product_tmpl_id', '=', product_tmpl_id), ('name', '=', partner_id.id)])
                ls_uoms = []
                for supplier_info in self.pool['product.supplierinfo'].browse(cr, uid, ls_supplier_info):
                    ls_uoms.extend(supplier_info.uom_ids)
                for uom in ls_uoms:
                    level = uom.level_uom
                    if level == 'level2':
                        uom_l2_id = uom.id
                    if level == 'level3':
                        uom_l3_id = uom.id
                    if level == 'level4':
                        uom_l4_id = uom.id
            new_quant = self.copy(cr, SUPERUSER_ID, quant.id, default={
                'qty': new_qty_round,
                'history_ids': [(4, x[0]) for x in res],
                'uom_l2_id': uom_l2_id,
                'uom_l3_id': uom_l3_id,
                'uom_l4_id': uom_l4_id
            }, context=context)
            self.write(cr, SUPERUSER_ID, quant.id, {
                'qty': qty_round,
                'uom_l2_id': uom_l2_id,
                'uom_l3_id': uom_l3_id,
                'uom_l4_id': uom_l4_id
            }, context=context)
        return self.browse(cr, uid, new_quant, context=context)


class br_stock_production_lot(models.Model):
    _inherit = 'stock.production.lot'

    br_supplier_id = fields.Many2one('res.partner', string="Supplier")


# FIXME: Why would we inherit stock picking here ?
class br_stock_picking(models.Model):
    _inherit = 'stock.picking'

    def create_lots_for_picking(self, cr, uid, ids, context=None):
        lot_obj = self.pool['stock.production.lot']
        opslot_obj = self.pool['stock.pack.operation.lot']
        to_unlink = []
        for picking in self.browse(cr, uid, ids, context=context):
            for ops in picking.pack_operation_ids:
                for opslot in ops.pack_lot_ids:
                    if not opslot.lot_id:
                        lot_id = lot_obj.create(cr, uid, {'name': opslot.lot_name,
                                                          'product_id': ops.product_id.id,
                                                          'br_supplier_id': opslot.br_supplier_id.id,
                                                          'removal_date': opslot.br_removal_date
                                                          },
                                                context=context)
                        opslot_obj.write(cr, uid, [opslot.id], {'lot_id': lot_id}, context=context)
                # Unlink pack operations where qty = 0
                to_unlink += [x.id for x in ops.pack_lot_ids if x.qty == 0.0]
        opslot_obj.unlink(cr, uid, to_unlink, context=context)
    calculate_total = fields.Boolean(string='Calculate Operation Total?', compute='_compute_calculate_operation_total')
    init_tub_total = fields.Float(string="Initial Total Tub", compute='_get_init_total', store=True)
    init_cake_total = fields.Float(string="Initial Total Cake", compute='_get_init_total', store=True)
    init_carton_total = fields.Float(string="Initial Total Full Carton", compute='_get_init_total', store=True)
    fulfill_tub_total = fields.Float(string="Fullfillment Total Tub", compute='_get_fulfill_total', store=True)
    fulfill_cake_total = fields.Float(string="Fullfillment Total Cake", compute='_get_fulfill_total', store=True)
    fulfill_carton_total = fields.Float(string="Fullfillment Total Full Carton", compute='_get_fulfill_total', store=True)

    @api.multi
    def _compute_calculate_operation_total(self):
        for picking in self:
            sql = ('''SELECT so.id 
                  FROM stock_picking sp 
                  JOIN sale_order so ON sp.group_id = so.procurement_group_id 
                  WHERE sp.id = %s''') % (picking.id)
            self.env.cr.execute(sql)
            result = self.env.cr.fetchone()
            picking.calculate_total = False
            if picking.request_id or picking.is_dispute_picking or (result and result[0]):
                picking.calculate_total = True

    @api.multi
    @api.depends('move_lines.product_uom_qty', 'state')
    def _get_init_total(self):
        """
        Get the initial total of tub, cake, and carton (Only applicable for Trade Sales, Outlet Ordering and Dispute
        Picking)
        :return:
        """
        for picking in self:
            if picking.calculate_total:
                picking.init_tub_total = 0
                picking.init_cake_total = 0
                picking.init_carton_total = 0
                if picking.move_lines:
                    for move in picking.move_lines:
                        if move.product_uom and move.product_uom.uom_total_type:
                            utt = move.product_uom.uom_total_type
                            if utt == 'tub_total':
                                picking.init_tub_total += move.product_uom_qty
                            elif utt == 'cake_total':
                                picking.init_cake_total += move.product_uom_qty
                            elif utt == 'carton_total':
                                picking.init_carton_total += move.product_uom_qty

    @api.multi
    @api.depends('pack_operation_ids.qty_done')
    def _get_fulfill_total(self):
        """
        Get the fulfilled total of tub, cake, and carton (Only applicable for Trade Sales, Outlet Ordering and Dispute
        Picking)
        :return:
        """
        for picking in self:
            if picking.calculate_total:
                picking.fulfill_tub_total = 0
                picking.fulfill_cake_total = 0
                picking.fulfill_carton_total = 0
                if picking.pack_operation_ids:
                    for operation in picking.pack_operation_ids:
                        if operation.product_uom_id and operation.product_uom_id.uom_total_type:
                            utt = operation.product_uom_id.uom_total_type
                            if utt == 'tub_total':
                                picking.fulfill_tub_total += operation.qty_done
                            elif utt == 'cake_total':
                                picking.fulfill_cake_total += operation.qty_done
                            elif utt == 'carton_total':
                                picking.fulfill_carton_total += operation.qty_done

    # @api.multi
    # @api.constrains('fulfill_tub_total', 'fulfill_cake_total', 'fulfill_carton_total')
    # def check_init_fulfill_total(self):
    #     """
    #     raise error when the fulfill total is more than initial total
    #     :return:
    #     """
    #     if self.state not in ('draft', 'confirmed'):
    #         if self.init_tub_total < self.fulfill_tub_total:
    #             raise ValidationError(_("Total tub in the operations is more than the initial demand!"))
    #         elif self.init_cake_total < self.fulfill_cake_total:
    #             raise ValidationError(_("Total cake in the operations is more than the initial demand!"))
    #         elif self.init_carton_total < self.fulfill_carton_total:
    #             raise ValidationError(_("Total full carton in the operations is more than the initial demand!"))

    @api.multi
    def update_init_fulfill_total(self):
        """
        recompute the initial total and fulfill total
        :return:
        """
        self._get_init_total()
        self._get_fulfill_total()