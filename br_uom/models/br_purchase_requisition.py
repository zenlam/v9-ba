from openerp import models, fields, api,_
from openerp.osv import osv, fields

class br_purchase_requisition_line(osv.osv):
    _inherit = "purchase.requisition.line"

    def onchange_product_id(self, cr, uid, ids, product_id, product_uom_id, parent_analytic_account, analytic_account, parent_date, date, context=None):
        result = super(br_purchase_requisition_line, self).onchange_product_id(cr, uid, ids, product_id, product_uom_id, parent_analytic_account, analytic_account, parent_date, date, context)

        if product_id:
            product = self.pool['product.product'].browse(cr, uid, product_id)
            product_tmpl_id = product.product_tmpl_id.id
            ls_supplier_info = self.pool['product.supplierinfo'].search(cr, uid,
                                                                        [('product_tmpl_id', '=', product_tmpl_id)],
                                                                        context
                                                                       )
            uom_default = False
            ls_uoms = []
            for supplier_info in self.pool['product.supplierinfo'].browse(cr, uid, ls_supplier_info):
                ls_uoms.extend(product.product_tmpl_id.uom_id)
                ls_uoms.extend(supplier_info.uom_ids)
                uom_default = supplier_info.product_uom
            # if ls_uoms:
            #     result['domain'] = {'product_uom_id': [('id', 'in', [uom.id for uom in ls_uoms])]}
            # else:
            #     result['domain'] = {'product_uom_id': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

            result['value'].update({'product_uom_id': (uom_default and uom_default.id) or (product.uom_po_id and product.uom_po_id.id) or (product.uom_id and product.uom_id.id) or False})

        return result

class br_purchase_requisition(models.Model):
    _inherit = "purchase.requisition"

    def _prepare_purchase_order(self, cr, uid, requisition, supplier, context=None):
        return {
            'origin': requisition.name,
            'date_order': requisition.date_end or fields.datetime.now(),
            'partner_id': supplier.id,
            'currency_id': (supplier.property_purchase_currency_id and supplier.property_purchase_currency_id.id) or (requisition.company_id and requisition.company_id.currency_id.id),
            'company_id': requisition.company_id.id,
            'fiscal_position_id': self.pool.get('account.fiscal.position').get_fiscal_position(cr, uid, supplier.id, context=context),
            'requisition_id': requisition.id,
            'notes': requisition.description,
            'picking_type_id': requisition.picking_type_id.id
        }

    def _prepare_purchase_order_line(self, cr, uid, requisition, requisition_line, purchase_id, supplier, context=None):
        vals = super(br_purchase_requisition, self)._prepare_purchase_order_line(cr, uid, requisition, requisition_line, purchase_id, supplier, context)
        if 'product_uom' in vals and 'product_qty' in vals:
            vals['product_uom'] = requisition_line.product_uom_id.id or requisition_line.product_id.uom_po_id.id
            vals['product_qty'] = requisition_line.product_qty
        return vals




