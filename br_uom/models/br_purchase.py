from openerp import models, fields, api, _

class br_po_order_line(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('product_id')
    def onchange_product_id(self):
        # FIXME: onchange function get old values from self
        result = super(br_po_order_line, self).onchange_product_id()
        # result = {}
        if self.product_id:
            self.name = self.product_id.name_template
            partner_id = self.order_id.partner_id.id
            product_tmpl_id = self.product_id.product_tmpl_id.id
            ls_supplier_info = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product_tmpl_id),
                                                                        ('name', '=', partner_id)]
                                                                       )
            uom_default = False
            ls_uoms = []
            for supplier_info in ls_supplier_info:
                ls_uoms.extend(self.product_id.product_tmpl_id.uom_id)
                ls_uoms.extend(supplier_info.uom_ids)
                uom_default = supplier_info.product_uom
            if ls_uoms:
                # self.product_uom = ls_uoms[0]
                result['domain'] = {'product_uom': [('id', 'in', [uom.id for uom in ls_uoms])]}
            else:
                # self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
                result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

            self.product_uom = uom_default or self.product_id.uom_po_id or self.product_id.uom_id or False

        return result


class BRPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.multi
    def button_confirm(self):
        res = super(BRPurchaseOrder, self.with_context(ADD_STP=False)).button_confirm()
        return res

    @api.multi
    def _add_supplier_to_product(self):
        if self.env.context.get('ADD_STP', True):
            super(BRPurchaseOrder, self)._add_supplier_to_product()

BRPurchaseOrder()

