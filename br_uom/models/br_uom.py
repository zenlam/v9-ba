from openerp.osv import osv, fields as old_fields
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError, UserError
from collections import Counter
import time
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.multi
    def _get_uom_by_type(self, type):
        """Get uom from vendor by its type"""
        for seller in self.seller_ids.sorted(key=lambda r: r.is_default):
            uom = seller._get_uom_by_type(type)
            if uom:
                return uom
        return self.uom_id


class br_product_product(osv.osv):
    _inherit = 'product.product'

    def _select_seller(self, cr, uid, product_id, partner_id=False, quantity=0.0,
                       date=time.strftime(DEFAULT_SERVER_DATE_FORMAT), uom_id=False, context=None):
        if context is None:
            context = {}
        res = self.pool.get('product.supplierinfo').browse(cr, uid, [])
        for seller in product_id.seller_ids:
            # Set quantity in UoM of seller
            quantity_uom_seller = quantity
            # Check if seller's uom is configured
            if quantity_uom_seller and uom_id and seller.product_uom and uom_id != seller.product_uom:
                quantity_uom_seller = uom_id._compute_qty_obj(uom_id, quantity_uom_seller, seller.product_uom)

            if seller.date_start and seller.date_start > date:
                continue
            if seller.date_end and seller.date_end < date:
                continue
            if partner_id and seller.name not in [partner_id, partner_id.parent_id]:
                continue
            if quantity_uom_seller < seller.qty:
                continue
            if seller.product_id and seller.product_id != product_id:
                continue
            res |= seller
            break
        return res


class br_product_supplierinfo(osv.osv):
    _inherit = 'product.supplierinfo'

    @api.multi
    def _get_product_uom_domain(self):
        context = self._context
        if 'default_product_tmpl_id' in context and context['default_product_tmpl_id']:
            product_tmpl_id = self.env['product.template'].browse(context['default_product_tmpl_id'])
            uom_category = product_tmpl_id.uom_id.category_id
            related_uoms = self.env['product.uom'].search(
                [('category_id', '=', uom_category.id)])
            return [('id', 'in', related_uoms.ids)]
        else:
            product_uom = self.env['product.uom'].search([])
            return [('id', 'in', product_uom.ids)]


    _columns = {
        'product_uom': old_fields.many2one('product.uom', domain=_get_product_uom_domain, string="Vendor Unit of Measure PO")
    }

class BrProductUOM(models.Model):
    _inherit = 'product.uom'

    def _compute_qty_obj(self, cr, uid, from_unit, qty, to_unit, round=True, rounding_method='UP', context=None):
        if from_unit.category_id.id != to_unit.category_id.id:
            if context.get('raise-exception', True):
                raise UserError(_('Conversion from Product UoM %s to Default UoM %s is not possible as they both belong to different Category!.\n Product: %s')
                                % (from_unit.name, to_unit.name, to_unit.category_id.name or from_unit.category_id.name))
        return super(BrProductUOM, self)._compute_qty_obj(cr, uid, from_unit, qty, to_unit, round, rounding_method, context)

    @api.constrains('factor')
    @api.multi
    def _check_factor(self):
        for u in self:
            if u.factor == 0:
                raise ValidationError("Factor must be greater than zero")

    @api.multi
    @api.depends('name', 'vendor_id')
    def name_get(self):
        result = []
        for r in self:
            name = r.name
            try:
                if r.vendor_id:
                    name += ' - %s' % r.vendor_id.name.name
            except:
                pass
            result.append((r.id, name))
        return result

    @api.model
    def _get_default_uom(self):
        context = self._context
        if 'default_uom_id' in context and context['default_uom_id']:
            product_uom = self.browse(context['default_uom_id'])
            return product_uom.category_id
        else:
            return False

    vendor_id = fields.Many2one('product.supplierinfo', string='Vendor')
    level_uom = fields.Selection([('level2', 'Level 2'), ('level3', 'Level 3'), ('level4', 'Level 4')])
    product_tmpl_id = fields.Many2one(comodel_name='product.template', string='Product')
    is_po_default = fields.Boolean(string='Is default', default=False)
    is_distribution = fields.Boolean(string='Distribution UOM', default=False)
    is_storage = fields.Boolean(string='Storage UOM', default=False)
    category_id = fields.Many2one('product.uom.categ', 'Unit of Measure Category', required=True, ondelete='cascade',
                                  help="Conversion between Units of Measure can only occur if they belong to the same category. The conversion will be made based on the ratios.",
                                  default=_get_default_uom)
    uom_total_type = fields.Selection([('tub_total', 'Tub Total'), ('cake_total', 'Cake Total'), ('carton_total', 'Full Carton Total')], 'UOM Total Type')
    is_ordering = fields.Boolean(string='Ordering UOM', default=False)

    _defaults = {
        'uom_type': ''
    }

    @api.model
    def create(self, vals):
        """
            - Add product template id
            - Add product uom category
            when create uom from vendor form
        """
        if 'product_tmpl_id' not in vals or not vals['product_tmpl_id']:
            if 'vendor_id' in vals and vals['vendor_id']:
                vendor = self.env['product.supplierinfo'].browse(vals['vendor_id'])
                product_tmpl = vendor.product_tmpl_id
                vals['product_tmpl_id'] = product_tmpl.id
                vals['category_id'] = product_tmpl.uom_id.category_id.id
        return super(BrProductUOM, self).create(vals)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        context = self._context
        if 'product_id' in context and context.get('product_id'):
            model_supplier = self.env['product.supplierinfo']
            product_id = context['product_id']
            product = self.env['product.product'].browse(product_id)
            vendor_id = context.get('vendor_id', None)
            if vendor_id:
                ls_supplier_info = model_supplier.browse(vendor_id)
            else:
                supplier_id = context.get('supplier_id', None)
                if supplier_id:
                    ls_supplier_info = model_supplier.search([
                        ('product_tmpl_id', '=', product.product_tmpl_id.id),
                        ('name', '=', supplier_id)
                    ])
                else:
                    ls_supplier_info = model_supplier.search(
                        [('product_tmpl_id', '=',
                          product.product_tmpl_id.id)
                         ])
            ls_uoms = []
            for supplier_info in ls_supplier_info:
                if supplier_info.uom_ids:
                    ls_uoms.extend(supplier_info.uom_ids)
            if ls_uoms:
                ls_uoms.extend(product.uom_id)
                args += [('id', 'in', [uom.id for uom in ls_uoms])]
                line_ids = self.search(args)
            else:
                args += [('category_id', '=', product.uom_id.category_id.id)]
                line_ids = self.search(args)
            return line_ids.name_get()
        return super(BrProductUOM, self).name_search(args=args, operator=operator, limit=limit)


class br_res_partner(models.Model):
    _inherit = 'product.supplierinfo'

    uom_ids = fields.One2many('product.uom', 'vendor_id', string='UOMs')

    @api.constrains('uom_ids')
    def check_uom_ids(self):
        self.check_valid_uom_level()
        self.check_valid_uom_type()

    @api.multi
    @api.depends('uom_ids')
    def _get_packing_size(self):
        for rec in self:
            result = ""
            for k, uom in enumerate(sorted(rec.uom_ids, key=lambda y: y.level_uom, reverse=True)):
                if uom and uom.factor != 0:
                    qty = uom._compute_qty_obj(uom, 1, uom.product_tmpl_id.uom_id, round=True, rounding_method='HALF-UP')
                    if uom.uom_type == 'smaller' and qty != 0:
                        qty = 1 / qty
                    if k == 0:
                        result += "1%s" % uom.name
                    else:
                        result += "*%s%s" % (qty_pre / qty, uom.name)
                    qty_pre = qty
            if len(result) > 0:
                result += "*%s%s" % (qty_pre, rec.uom_ids[0].product_tmpl_id.uom_id.name)
            rec.packing_size = result

    packing_size = fields.Char(string='Packing Size', compute=_get_packing_size)

    def check_valid_uom_level(self):
        """There can be only one uom level per product"""
        uom_level_map = dict(self.uom_ids._columns['level_uom'].selection)
        check_list = []
        for l in self.uom_ids:
            if l.level_uom not in check_list:
                check_list.append(l.level_uom)
            else:
                raise ValidationError(_("Not allow set uom %s > 1 time" % uom_level_map[l.level_uom]))

    def check_valid_uom_type(self):
        """There can be only one uom type per product"""
        uom_types = ['purchase', 'distribution', 'storage']
        tmp = []
        for l in self.uom_ids:
            if l.is_po_default:
                tmp.append('purchase')
            if l.is_distribution:
                tmp.append('distribution')
            if l.is_storage:
                tmp.append('storage')

        redundant_types = ["1 %s UOM" % k for k, v in Counter(tmp).items() if v > 1]
        if redundant_types:
            message = ", ".join(redundant_types)
            raise ValidationError("1 Product can only have %s in 1 vendor" % message)

        if self.uom_ids:
            missing_types = ["1 %s UOM" % k for k in uom_types if k not in tmp]
            if missing_types:
                message = ", ".join(missing_types)
                raise ValidationError("You must select %s for this vendor" % message)

    @api.onchange('uom_ids')
    def onchange_uom_ids(self):
        self.check_valid_uom_level()
        self.check_valid_uom_type()

    @api.multi
    def _get_uom_by_type(self, uom_type):
        """Get uom from partner"""
        if uom_type == 'standard':
            return self.product_tmpl_id.uom_id
        else:
            uom_type_map = {
                'purchase': 'is_po_default',
                'storage': 'is_storage',
                'distribution': 'is_distribution',
            }
            for u in self.uom_ids:
                if getattr(u, uom_type_map[uom_type]):
                    return u
        return self.product_tmpl_id.uom_id

    @api.multi
    def get_uom_by_levels(self, levels=False):
        uoms = {}
        for uom in self.uom_ids:
            if not levels or uom.level_uom in levels:
                uoms[uom.level_uom] = uom
        return uoms