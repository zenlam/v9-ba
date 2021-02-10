from openerp import fields, models, api, _
from openerp.osv import fields as OFields
from openerp.exceptions import UserError


class StockPackOperation(models.Model):
    _inherit = "stock.pack.operation"

    vendor_id = fields.Many2one('res.partner', string=_('Vendor'))
    vendor_count = fields.Integer(_('Product Vendor Count'), compute='_compute_vendor_count')
    pack_lot_ids= fields.One2many('stock.pack.operation.lot', 'operation_id', 'Expiry Date', oldname='pack_lot_ids')

    def show_details2(self, cr, uid, ids, context=None):
        data_obj = self.pool['ir.model.data']
        view = data_obj.xmlid_to_res_id(cr, uid, 'br_stock.view_pack_operation_details_form_save_inherit')
        pack = self.browse(cr, uid, ids[0], context=context)
        return {
             'name': _('Operation Details'),
             'type': 'ir.actions.act_window',
             'view_type': 'form',
             'view_mode': 'form',
             'res_model': 'stock.pack.operation',
             'views': [(view, 'form')],
             'view_id': view,
             'target': 'new',
             'res_id': pack.id,
             'context': context,
        }

    def split_lot(self, cr, uid, ids, context=None):
        res = super(StockPackOperation, self).split_lot(cr, uid, ids, context=context)
        res['name'] = 'Expiry Details'
        return res

    def _compute_lots_visible(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for pack in self.browse(cr, uid, ids, context=context):
            if pack.pack_lot_ids:
                res[pack.id] = True
                continue
            pick = pack.picking_id
            product_requires = pack.product_id._check_need_tracking(pack)
            if pick.picking_type_id:
                res[pack.id] = (pick.picking_type_id.use_existing_lots or pick.picking_type_id.use_create_lots) and product_requires
            else:
                res[pack.id] = product_requires
        return res

    _columns = {
        'lots_visible': OFields.function(_compute_lots_visible, type='boolean'),
    }

    @api.onchange('product_uom_id')
    def _onchange_product_uom_id(self):
        if self.product_uom_id and self.product_id and self.picking_id:
            if self.picking_id.origin and self.picking_id.origin.startswith('PO'):
                purchase_order = self.env['purchase.order'].search([('name','=',self.picking_id.origin)])
                if purchase_order:
                    uom_ids = []
                    for line in purchase_order.order_line:
                        if line.product_id == self.product_id:
                            uom_ids.append(line.product_uom.id)
                    if uom_ids and self.product_uom_id.id not in uom_ids:
                        warning_mess = {
                                    'title': _('Different UOM!'),
                                    'message' : _('You have select the UOM that is different from the Purchased.')
                                    }
                        return {'warning': warning_mess}
                        
                            
            
    @api.multi
    @api.depends('product_id')
    def _compute_vendor_count(self):
        for m in self:
            found = 0
            if m.product_id and m.product_id.tracking == 'none':
                for vendor in m.product_id.seller_ids:
                    if len(vendor.uom_ids) > 0:
                        found = 1
                        break
            m.vendor_count = found

    @api.multi
    def save(self):
        for pack in self:
            if pack.product_id._check_need_tracking(pack):
                qty_done = sum([x.qty for x in pack.pack_lot_ids])
                pack.write({'qty_done': qty_done})
        return {'type': 'ir.actions.act_window_close'}

    def product_id_change(self, cr, uid, ids, product_id, product_uom_id, product_qty, context=None):
        res = self.on_change_tests(cr, uid, ids, product_id, product_uom_id, product_qty, context=context)
        uom_obj = self.pool['product.uom']
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        if product_id and not product_uom_id or uom_obj.browse(cr, uid, product_uom_id, context=context).category_id.id != product.uom_id.category_id.id:
            res['value']['product_uom_id'] = product.uom_id.id
        if product:
            res['value']['lots_visible'] = product._check_need_tracking()#(product.tracking != 'none')
            res['domain'] = {'product_uom_id': [('category_id', '=', product.uom_id.category_id.id)]}
        else:
            res['domain'] = {'product_uom_id': []}
        return res

    def check_tracking(self, cr, uid, ids, context=None):
        """ Checks if serial number is assigned to stock move or not and raise an error if it had to.
        """
        operations = self.browse(cr, uid, ids, context=context)
        for ops in operations:
            if ops.picking_id and (ops.picking_id.picking_type_id.use_existing_lots or ops.picking_id.picking_type_id.use_create_lots) and \
                    ops.product_id and ops.qty_done > 0.0 and ops.product_id._check_need_tracking(ops):
                if not ops.pack_lot_ids:
                    raise UserError(_('You need to provide a Expiry Date for product %s') % ops.product_id.name)
                if ops.product_id.tracking == 'serial':
                    for opslot in ops.pack_lot_ids:
                        if opslot.qty not in (1.0, 0.0):
                            raise UserError(_('You should provide a different serial number for each piece'))
