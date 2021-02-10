# -*- coding: utf-8 -*-

from collections import Counter

from openerp import api, fields, models
from openerp.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_default_ordering_uom = fields.Boolean('Standard UOM as Ordering UOM?')


class BrProductUOM(models.Model):
    _inherit = 'product.uom'

    @api.multi
    def name_get(self):
        result = []
        for r in self:
            name = r.name
            if r.vendor_id and not self._context.get('from_request_uom'):
                name += ' - %s' % r.sudo().vendor_id.name.name
            result.append((r.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        uom_type = self.env.context.get('uom_type', False)
        if uom_type and uom_type == 'ordering':
            product_id = self.env.context.get('product_id', False)
            if product_id:
                product = self.env['product.product'].browse(product_id)
                seller = product.seller_ids.filtered(lambda r: r.is_default)
                if seller:
                    recs |= seller.uom_ids.filtered(lambda r: r.is_ordering)
                    if product.product_tmpl_id.is_default_ordering_uom:
                        recs |= product.uom_id
                    return recs.with_context(from_request_uom=True).name_get()
                else:
                    return super(BrProductUOM, self).name_search(name=name, args=args, operator=operator, limit=limit)
            else:
                return super(BrProductUOM, self).name_search(name=name, args=args, operator=operator, limit=limit)
        return super(BrProductUOM, self).name_search(name=name, args=args, operator=operator, limit=limit)


class StockRequest(models.Model):
    _inherit = 'br.stock.request.form'

    @api.onchange('product_categ_ids')
    def onchange_product_categ_ids(self):
        vals = []
        existing_products = []
        products = self.env['product.product'].search(
            [('categ_id', 'child_of', self.product_categ_ids.ids)])
        # Fetch all products from selected category(s)
        for l in self.line_ids:
            # If product not in category and isn't added to lines manually then remove it
            if l.product_id.id not in products.ids and not l.auto_added:
                vals.append(
                    (3, l.id, 0)
                )
            else:
                vals.append((0, 0, {
                    'product_id': l.product_id.id,
                    'uom_type': l.uom_type,
                    'auto_added': True
                }))
            existing_products.append(l.product_id.id)
        for p in products:
            if p.id not in existing_products:
                # By default uom type is standard, if uom is configured in any vendor then set uom type to distribution
                uom_type = 'ordering'
                # sellers = p.seller_ids
                # if sellers:
                #     for s in sellers:
                #         if s.uom_ids:
                #             uom_type = 'ordering'
                #             break
                vals.append((0, 0, {
                    'product_id': p.id,
                    'uom_type': uom_type,
                    'auto_added': True
                }))
        if vals:
            self.line_ids = vals


class StockRequestTransfer(models.Model):
    _inherit = 'br.stock.request.transfer'

    @api.onchange('form_id')
    def onchange_form_id(self):
        lines = [(5, False, False)]
        if self.form_id:
            for l in self.form_id.line_ids_related:
                # Get uom from vendors
                uom_id = False
                sellers = l.product_id.seller_ids.filtered(lambda r: r.is_default)
                if l.uom_type == 'standard':
                    uom_id = l.product_id.uom_id.id
                else:
                    uom_type_map = {
                        'purchase': 'is_po_default',
                        'storage': 'is_storage',
                        'distribution': 'is_distribution',
                        'ordering': 'is_ordering'
                    }
                    for s in sellers:
                        for u in s.uom_ids:
                            # Select first uom which has same uom type in transfer line
                            if getattr(u, uom_type_map[l.uom_type]):
                                uom_id = u.id
                                break
                    if not uom_id:
                        uom_id = l.product_id.uom_id.id
                val = {
                    'product_id': l.product_id.id,
                    'uom_id': uom_id,
                    'uom_type': l.uom_type
                }
                lines.append((0, 0, val))
        self.line_ids = lines
        self.recompute_qty_on_hand()
        if self.form_id and len(self.form_id.warehouse_ids) == 1:
            self.warehouse_id = self.form_id.warehouse_ids.id


class StockRequestLine(models.Model):
    _inherit = 'br.stock.request.form.line'

    uom_type = fields.Selection(selection_add=[('ordering', 'UoM Ordering')], default="ordering", readonly=True)


class StockRequestTransferLine(models.Model):
    _inherit = 'br.stock.request.transfer.line'

    uom_type = fields.Selection(selection_add=[('ordering', 'UoM Ordering')], default="ordering", readonly=True)


class br_res_partner(models.Model):
    _inherit = 'product.supplierinfo'

    def check_valid_uom_type(self):
        """There can be only one uom type per product"""
        uom_types = ['purchase', 'distribution', 'storage', 'ordering']
        tmp = []
        for l in self.uom_ids:
            if l.is_po_default:
                tmp.append('purchase')
            if l.is_distribution:
                tmp.append('distribution')
            if l.is_storage:
                tmp.append('storage')
            if l.is_ordering:
                tmp.append('ordering')

        redundant_types = ["1 %s UOM" % k for k, v in Counter(tmp).items() if v > 1 and k != 'ordering']
        if redundant_types:
            message = ", ".join(redundant_types)
            raise ValidationError("1 Product can only have %s in 1 vendor" % message)

        if self.uom_ids:
            missing_types = ["1 %s UOM" % k for k in uom_types if k not in tmp]
            if missing_types:
                message = ", ".join(missing_types)
                raise ValidationError("You must select %s for this vendor" % message)
