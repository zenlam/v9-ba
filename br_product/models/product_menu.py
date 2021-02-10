# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.exceptions import UserError, ValidationError
from openerp.osv import osv, fields as old_fields


class product_supplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    vendor_currency = fields.Many2one('res.currency')
    shipment_info = fields.Char(string="Shipment Information")


class product_template(osv.osv):
    _inherit = 'product.template'

    _columns = {
        'default_code': old_fields.related('product_variant_ids',
                                           'default_code', type='char',
                                           string='Internal Product Code'),
    }


class product_template(models.Model):
    _inherit = 'product.template'

    is_menu = fields.Boolean()
    partner_ids = fields.One2many(comodel_name='res.partner', compute='_get_partner_ids')
    is_asset = fields.Boolean('Is Asset?', default=True)
    asset_category_id = fields.Many2one(comodel_name='account.asset.category', oldname='asset_category_id',
                                        company_dependent=True)
    product_id = fields.Char(string="Product ID", compute='get_product_id')
    product_xml_id = fields.Char(
        string="Product Long ID",
        help="Record will not have an XML ID until it has been exported.",
        compute='get_product_id')

    internal_prod_type = fields.Char(string="Internal Product Type")
    custom_code = fields.Char(string="Custom Code")
    duty = fields.Char(string="Duty")
    storage_practice = fields.Char(string="Storage Practice")
    buy_practice = fields.Char(string="Buy Practice")
    count_practice = fields.Char(string="Count Practice")

    # rename base fields for filter
    name = fields.Char(string="Product Name")
    available_in_pos = fields.Boolean(string="Available at POS")
    categ_id = fields.Many2one(string="Product Category")

    @api.model
    def create(self, vals):
        if 'name' in vals:
            vals.update(name=" ".join(vals['name'].split()))
        return super(product_template, self).create(vals)

    @api.multi
    def write(self, vals):
        if 'name' in vals:
            vals.update(name=" ".join(vals['name'].split()))
        return super(product_template, self).write(vals)

    @api.constrains('name', 'default_code')
    def check_unique_name_reference(self):
        all_product = self.env['product.template'].search([])
        if all_product:
            for product in all_product:
                if self.id == product.id:
                    continue
                elif self.name and self.name.replace(" ", "").lower() == product.name.replace(" ", "").lower():
                    raise ValidationError(_("Product name exists!"))
                elif self.default_code and product.product_variant_ids.default_code and \
                        self.default_code.replace(" ", "").lower() == product.product_variant_ids.default_code.replace(" ", "").lower():
                    raise ValidationError(_("Internal reference exists!"))

    @api.multi
    def _get_partner_ids(self):
        for p in self:
            partners = self.env['res.partner']
            for seller in p.seller_ids:
                partners |= seller.name
            p.partner_ids = partners

    # TODO: Check if there is anywhere that needs product.template as menu name ?
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        args.extend([('is_menu', '=', False)])
        return super(product_template, self).search(cr, user, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def _get_uom_id(self, cr, uid, context):
        uom_id = None
        if context.get('load_menu_name', False):
            uom_id = self.pool["product.uom"].search(cr, uid, [], limit=1, order='id')[0]
        return uom_id

    _defaults = {
        'uom_id': _get_uom_id,
        'list_price': 0
    }

    @api.onchange('asset_category_id')
    def onchange_asset(self):
        if self.asset_category_id:
            self.property_account_expense_id = self.asset_category_id.account_depreciation_id

    @api.onchange('seller_ids')
    def onchange_seller_ids(self):
        self._check_seller_ids()

    @api.one
    @api.constrains('seller_ids')
    def _check_seller_ids(self):
        count = len(self.seller_ids.filtered(lambda x: x.is_default))
        if count > 1:
            raise ValidationError(_("There can be only one default supplier"))

    def get_default_supplier(self):
        """Get default seller"""
        if 'COMPANY_ID' in self._context:
            company_id = self._context['COMPANY_ID']
            return self.seller_ids.filtered(lambda x: (x.is_default and x.company_id.id == company_id)) or False
        return self.seller_ids.filtered(lambda x: x.is_default) or False

    def get_supplier(self):
        """ Get supplier if the stock operation has no vendor_id (get default or random)"""
        if self.seller_ids:
            return self.seller_ids.filtered(lambda x: x.is_default) or self.seller_ids[0]
        return False

    @api.one
    def get_product_id(self):
        external_id = self.get_external_id()
        if external_id:
            for key in external_id:
                self.product_id = key
                self.product_xml_id = external_id[key]

    def _get_product_template_type(self, cr, uid, context=None):
        res = super(product_template, self)._get_product_template_type(cr, uid, context=context)
        if 'product' in [item[0] for item in res]:
            res.remove(('product', _('Stockable Product')))
            res.append(('product', _('Stockable')))
        return res


class product_menu(models.Model):
    _inherit = 'product.product'

    is_menu = fields.Boolean(related='product_tmpl_id.is_menu', store=True)

    product_recipe_lines = fields.One2many(
        comodel_name='br.menu.name.recipe',
        inverse_name='product_menu_id',
        string='Product Group')

    menu_category_id = fields.Many2one(comodel_name='br.menu.category', string='Menu Category', ondelete='restrict')

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        if context and not context.get('load_menu_name', False):
            args.extend([('is_menu', '=', False)])
        return super(product_menu, self).search(cr, user, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def _check_need_tracking(self, *args):
        return self.tracking != 'none'

    @api.model
    def create(self, vals):
        if 'name' in vals:
            vals.update(name=" ".join(vals['name'].split()))
        return super(product_menu, self).create(vals)

    @api.multi
    def write(self, vals):
        if 'name' in vals:
            vals.update(name=" ".join(vals['name'].split()))
        return super(product_menu, self).write(vals)

    @api.multi
    @api.constrains('name', 'default_code')
    def check_unique_name_reference(self):
        all_product = self.env['product.product'].search([])
        if all_product:
            for product in all_product:
                if self.id == product.id:
                    continue
                elif self.name and self.name.replace(" ", "").lower() == product.name.replace(" ", "").lower():
                    raise ValidationError(_("Product name exists!"))
                elif self.default_code and product.product_variant_ids.default_code and \
                        self.default_code.replace(" ", "").lower() == product.product_variant_ids.default_code.replace(
                    " ", "").lower():
                    raise ValidationError(_("Internal reference exists!"))
