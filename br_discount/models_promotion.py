# -*- coding: utf-8 -*-
from openerp.osv import osv
from openerp import models, fields, api, tools
import openerp.addons.decimal_precision as dp
from openerp.exceptions import ValidationError
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
import openerp
from openerp import models, fields, api, SUPERUSER_ID, _

from datetime import datetime
from openerp.osv.fields import one2many

PERCENTAGE = 1
FIXED_AMOUNT = 2

class BRPromotionCategory(models.Model):
    _name = 'br.promotion.category'

    @api.multi
    @api.depends('name', 'parent_id')
    def name_get(self):
        result = []
        for r in self:
            names = [r.name]
            pcat = r.parent_id
            while pcat:
                names.append(pcat.name)
                pcat = pcat.parent_id
            r.complete_name = ' / '.join(reversed(names))
            result.append((r.id, ' / '.join(reversed(names))))
        return result

    @api.multi
    def _name_get_fnc(self):
        return self.name_get()

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    active = fields.Boolean(string="Active", default=True)
    parent_id = fields.Many2one(comodel_name='br.promotion.category', string='Parent Category', ondelete='restrict')
    # TODO: rename to child_ids
    child_id = fields.One2many('br.promotion.category', 'parent_id', string='Children Categories')
    complete_name = fields.Char(string='Name', compute=name_get, store=True)

    _constraints = [
        (osv.osv._check_recursion, 'Error ! You cannot create recursive categories.', ['parent_id'])
    ]

    @api.multi
    def unlink(self):
        categ_ids = self.ids

        def get_child_categ(categ):
            if not categ.child_id:
                return
            for c in categ.child_id:
                categ_ids.append(c.id)
                get_child_categ(c)

        # Get all category(s) and its children
        for categ in self:
            get_child_categ(categ)
        promotions = self.env['br.bundle.promotion'].search([('promotion_category_id', 'in', categ_ids)])
        if len(promotions) > 0:
            raise ValidationError("Cannot delete this category(s), they are being used in some discounts!")
        return super(BRPromotionCategory, self).unlink()


BRPromotionCategory()


class BrBundlePromotionProduct(models.Model):
    _name = 'br.bundle.promotion.product'
    product_bundle_promotion_id = fields.Many2one(
        comodel_name='br.bundle.promotion',
        string='Product Promotion')

    bundle_promotion_id = fields.Many2one(
        comodel_name='br.bundle.promotion',
        string='Bundle Promotion')

    pos_category_id = fields.Many2many(
        comodel_name='pos.category',
        string='Pos Product Category', ondelete='restrict')

    product_id = fields.Many2many(
        comodel_name='product.product',
        string='Product')

    quota = fields.Integer(string='Quota')
    min_spending = fields.Float(string='Min Spending', default=0)
    min_quantity = fields.Integer(string='Min Quantity', default=1)
    discount = fields.Float(
        string='Discount (%)',
        digits_compute=dp.get_precision('Account'))
    discount_amount = fields.Float(
        string='Discount amount',
        digits_compute=dp.get_precision('Account'))
    bundle_item = fields.Boolean(string='Bundle item', default=True)

    @api.one
    @api.constrains('min_quantity')
    def _validate_check_min_quantity(self):
        if self.min_quantity < 0:
            raise ValidationError(
                'Quantity should not be equal or less than 0!')

    @api.one
    @api.constrains('discount_amount')
    def _validate_check_discount_amount(self):
        if self.discount_amount < 0:
            raise ValidationError(
                'Discount amount should not be equal or less than 0!')

    @api.one
    @api.constrains('discount')
    def _validate_check_discount(self):
        if 100 < self.discount or self.discount < 0:
            raise ValidationError('Discount (%) value ranging from 0 to 100 !')

    def get_parent_category(self, categ_id, parent_ids=[]):
        if categ_id:
            if categ_id.parent_id:
                parent_ids.append(categ_id.parent_id.id)
                self.get_parent_category(categ_id.parent_id, parent_ids)
            else:
                return parent_ids


    @api.one
    @api.constrains('product_id', 'pos_category_id')
    def _validate_check_product(self):
        if self.product_id and self.pos_category_id:
            raise ValidationError(
                'Only add items in either Product or Category')
        if self.pos_category_id:
            all_parent_ids = []
            for pos_cat_id in self.pos_category_id:
                self.get_parent_category(pos_cat_id, all_parent_ids)
            
            for pos_cat_id in self.pos_category_id:
                if pos_cat_id.id in all_parent_ids:
                    raise ValidationError('Parent and Child POS category can not be set together in one discount line !')

    @api.one
    @api.constrains('discount', 'discount_amount')
    def _validate_check_discount(self):
        if self.discount and self.discount_amount:
            raise ValidationError(
                'Only set value either for Discount (%) or Discount amount!')

    @api.one
    @api.constrains('min_quantity', 'min_spending')
    def _validate_check_quantity_spending(self):
        if self.min_quantity and self.min_spending:
            raise ValidationError(
                'Only set value either for Min Quantity or Min Spending!')


BrBundlePromotionProduct()


class BrVoucher(models.Model):
    _name = 'br.config.voucher'

    promotion_id = fields.Many2one(comodel_name='br.bundle.promotion', string='Promotion', required=1, ondelete='restrict')
    voucher_code = fields.Char(string='Voucher Code', required=1)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Customer')
    start_date = fields.Date(string='Start Date', required=1)
    end_date = fields.Date(string='End Date')
    date_red = fields.Date(string='Date Redeemed')
    status = fields.Selection([('available', 'Available'), ('expired', 'Expired'), ('redeemed', 'Redeemed')], 'Status',
                              default='available', required=1)
    validation_code = fields.Char(string='Validation Code')
    voucher_validation_code = fields.Char(compute='_get_unique_voucher_validation_code', store=True)
    sequence = fields.Integer(string='Sequence')
    order_ids = fields.Many2many(comodel_name='pos.order', string='Pos Order')
    order_id = fields.Many2one('pos.order', string='Pos order')
    remarks = fields.Char(string='Remarks')
    approval_no = fields.Char(string='Approval No')
    outlet_id = fields.Many2one('br_multi_outlet.outlet', string='Outlet Name', related='order_id.outlet_id',
                                store=True)

    @api.depends('voucher_code','validation_code')
    def _get_unique_voucher_validation_code(self):
        for voucher in self:
            voucher.voucher_validation_code = (voucher.voucher_code or '') + (voucher.validation_code or '')

    @api.model
    def get_promotion_from_voucher(self, voucher_validation_code, outlet):
        promotion = False
        voucher = self.search([('voucher_validation_code', '=', voucher_validation_code)], limit=1)
        if voucher:
            cur_date = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
            start_date = voucher.start_date
            end_date = voucher.end_date

            if start_date > cur_date:
                raise ValidationError('Can only redeem voucher after %s !!' % start_date)
            elif voucher.status == 'redeemed':
                raise ValidationError('Coupon/voucher code is redeemed on %s at outlet %s!' % (voucher.date_red, voucher.order_id.outlet_id.name))
            elif (end_date and cur_date > end_date) or voucher.status == 'expired':
                raise ValidationError('Coupon/voucher expired!')
            cur_promotion = voucher.promotion_id
            if cur_promotion.is_all_outlet:
                promotion = cur_promotion
            elif outlet in [x.outlet_id.id for x in cur_promotion.outlet_quota_lines]:
                promotion = cur_promotion
            else:
                raise ValidationError('Outlet is not valid!!')
        else:
            raise ValidationError('Voucher code does not exist!')

        if promotion:
            return [promotion.id, voucher.voucher_validation_code]
        else:
            return []

    @api.model
    def br_scheduler_update_status_voucher(self):
        result = self.search(
            [('end_date', '<', datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)), ('status', '=', 'available')])
        if result:
            vals = {
                'status': 'expired',
            }
            result.write(vals)
        return True

    @api.multi
    def unlink(self):
        msg1 = "Sorry, you don't have the access right to delete vouchers !"
        msg2 = "You can't delete vouchers that is redeemed and expired !"
        if not self.env.user.has_group('br_discount.group_voucher_modify_delete'):
            raise ValidationError(_(msg1))
        for voucher in self:
            if voucher.status in ('redeemed', 'expired'):
                raise ValidationError(_(msg2))
        return super(BrVoucher, self).unlink()


BrVoucher()


class BrBundlePromotionTime(models.Model):
    _name = 'br.bundle.promotion.time'

    bundle_promotion_id = fields.Many2one(
        comodel_name='br.bundle.promotion',
        string='Bundle Promotion')
    bundle_promotion_week_id = fields.Many2one(
        comodel_name='br.bundle.promotion',
        string='Bundle Promotion Week')
    bundle_promotion_month_id = fields.Many2one(
        comodel_name='br.bundle.promotion',
        string='Bundle Promotion Month')
    bundle_promotion_year_id = fields.Many2one(
        comodel_name='br.bundle.promotion',
        string='Bundle Promotion Year')

    date = fields.Date(string='Date', copy=False)
    start_hour = fields.Float('Start hour')
    end_hour = fields.Float(string='End hour')
    day_of_month = fields.Integer(string='Day of Month')

    @api.one
    @api.constrains('start_hour', 'end_hour')
    def onchange_time(self):
        if self.start_hour >= 24 or self.end_hour >= 24:
            raise ValidationError('Time ranging from 00:00 to 23:59 !')
        if self.start_hour < 0 or self.end_hour < 0:
            raise ValidationError('Time ranging from 00:00 to 23:59 !')
        if self.end_hour < self.start_hour:
            raise ValidationError('Start hour must less than End hour')


class BrBundlePromotion(models.Model):
    _name = 'br.bundle.promotion'
    _inherit = ['mail.thread']
    _description = 'Promotion'

    name = fields.Char(string='Display Promo Name', required=1, track_visibility='always')
    real_name = fields.Char(string='Name', required=1, track_visibility='always')
    code = fields.Char(string='Discount ID', track_visibility='always')
    code_sequence = fields.Char(string="Sequence", help="Sequence at the time generate code", track_visibility='always')
    active = fields.Boolean(string='Active', default=True, track_visibility='always')
    start_date = fields.Date(string='Start date', required=True, index=True, copy=False,
                             default=fields.Date.context_today, track_visibility='always')
    end_date = fields.Date(string='End date', track_visibility='always')
    # Using numeric as selection value huh, what's about the readability ?
    type_promotion = fields.Selection([(1, 'Bill Discount'),
                                       (2, 'Product Discount'),
                                       (3, 'Bundle Discount')], string='Promotion Type', required=True, default=1, track_visibility='onchange')
    image = fields.Binary(string='Image', help='Promotion Image', track_visibility='always')

    is_all_outlet = fields.Boolean(string="Is All Outlets", default=True, track_visibility='always')

    minimum_spending = fields.Float(string='Minimum Spending', track_visibility='always')
    # Add Bool voucher
    is_voucher = fields.Boolean(string="Use Code", track_visibility='always')
    fiscal_position_ids = fields.Many2one(comodel_name='account.fiscal.position', string='Fiscal Positions', track_visibility='always')

    promotion_category_id = fields.Many2one(
        comodel_name='br.promotion.category',
        string='Promotion Category',
        required=True,
        ondelete='restrict', track_visibility='always')

    voucher_ids = fields.One2many(
        comodel_name='br.config.voucher',
        inverse_name='promotion_id',
        string='Voucher')

    # Tab Product Promotion
    product_promotion_ids = fields.One2many(
        comodel_name='br.bundle.promotion.product',
        inverse_name='product_bundle_promotion_id',
        string="Product Promotion", copy=True)

    # Tab Bundle Promotion
    bundle_promotion_ids = fields.One2many(
        comodel_name='br.bundle.promotion.product',
        inverse_name='bundle_promotion_id',
        string='Bundle Promotion Product', copy=True, track_visibility='onchange')
    # Tab Bill Discount
    is_apply = fields.Boolean(string="Apply with other promotion", track_visibility='always')
    discount_type = fields.Selection([(1,
                                       'Percentage'),
                                      (2,
                                       'Fixed Amount')],
                                     string='Discount Type',
                                     required=True,
                                     default=1, track_visibility='onchange')
    discount_amount = fields.Float(string='Discount Amount', required=True, track_visibility='always')
    # Tab Outlet
    outlet_ids = fields.Many2many('br_multi_outlet.outlet')
    outlet_quota_reset = fields.Selection(string="Outlet Quota Reset",
                                          selection=[
                                              ('daily', 'Daily'),
                                              ('weekly', 'Weekly'),
                                              ('monthly', 'Monthly'),
                                              ('yearly', 'Yearly'),
                                          ], track_visibility='onchange')
    #     # Tab Time
    # For Week
    is_monday = fields.Boolean(string="Monday", track_visibility='always')
    is_tuesday = fields.Boolean(string="Tuesday", track_visibility='always')
    is_wednesday = fields.Boolean(string="Wednesday", track_visibility='always')
    is_thursday = fields.Boolean(string="Thursday", track_visibility='always')
    is_friday = fields.Boolean(string="Friday", track_visibility='always')
    is_saturday = fields.Boolean(string="Saturday", track_visibility='always')
    is_sunday = fields.Boolean(string="Sunday", track_visibility='always')
    recurring = fields.Selection([(1, 'By Week'), (2, 'By Month'),
                                  (3, 'By Year')], string='Recurring', default=None, track_visibility='onchange')

    bundle_promotion_time_ids = fields.One2many(
        comodel_name='br.bundle.promotion.time',
        inverse_name='bundle_promotion_id',
        string='Bundle promotion time')
    bundle_promotion_time_week_ids = fields.One2many(
        comodel_name='br.bundle.promotion.time',
        inverse_name='bundle_promotion_week_id',
        string='Bundle promotion time Week')
    bundle_promotion_time_month_ids = fields.One2many(
        comodel_name='br.bundle.promotion.time',
        inverse_name='bundle_promotion_month_id',
        string='Bundle promotion time Month')
    bundle_promotion_time_year_ids = fields.One2many(
        comodel_name='br.bundle.promotion.time',
        inverse_name='bundle_promotion_year_id',
        string='Bundle promotion time Year')

    instruction = fields.Text(string='Instruction', track_visibility='always')

    image_medium = openerp.fields.Binary("Medium-sized image",
                                         compute='_compute_images', inverse='_inverse_image_medium', store=True,
                                         attachment=True,
                                         help="Medium-sized image of the category. It is automatically " \
                                              "resized as a 128x128px image, with aspect ratio preserved. " \
                                              "Use this field in form views or some kanban views.")

    image_small = openerp.fields.Binary("Small-sized image",
                                        compute='_compute_images', inverse='_inverse_image_small', store=True,
                                        attachment=True,
                                        help="Small-sized image of the category. It is automatically " \
                                             "resized as a 64x64px image, with aspect ratio preserved. " \
                                             "Use this field anywhere a small image is required.")

    is_non_sale_trans = fields.Boolean(string="Is Non-Sale Transaction", track_visibility='always')
    is_smart_detection = fields.Boolean(string="Smart Detection", track_visibility='always')
    user_group_ids = fields.Many2many(
        'br.discount.group',
        string='Employee Group',
        help='User Group apply promotion', ondelete='restrict')

    # Sales voucher fields
    payment_method = fields.Many2one('account.journal', string=_("Payment Method"), track_visibility='always')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', track_visibility='always')
    is_hq_voucher = fields.Boolean(string=_("Is Redemption"), default=False, track_visibility='always')
    credit_account_id = fields.Many2one('account.account', string="Sales Credit Account", track_visibility='always')
    debit_account_id = fields.Many2one('account.account', string="Sales Debit Account", track_visibility='always')
    order_lines = fields.Many2many(
        'pos.order.line', 'pos_order_line_promotion_default_rel',
        'promotion_id', 'pos_order_line_id',
        string='Pos Order Line', copy=False)
    last_voucher_sequence = fields.Integer(string='Last Voucher Sequence',
                                           default=0)

    @api.multi
    def unlink(self):
        for promo in self:
            if len(promo.order_lines) != 0:
                raise ValidationError(_("You can't delete promotion that linked to pos order line !"))
        return super(BrBundlePromotion, self).unlink()

    @api.constrains('payment_method')
    def onchange_payment_method(self):
        # Each time change payment method for voucher need to update payment method on pos config also
        if self.is_hq_voucher:
            outlet_ids = [x.outlet_id.id for x in self.outlet_quota_lines]
            pos_configs = self.env['pos.config'].search([('outlet_id', 'in', outlet_ids)])
            missing_configs = []
            for config in pos_configs:
                found = config.journal_ids.filtered(lambda x: x.id == self.payment_method.id)
                if not found:
                    missing_configs.append(config.outlet_id.name)
            if missing_configs:
                message = "Must config this payment for following outlet(s): \n - %s" % "\n - ".join(missing_configs)
                raise ValidationError(_(message))

    @api.onchange('is_hq_voucher')
    def onchange_is_hq_voucher(self):
        # If voucher is HQ Voucher, discount type must be fixed amount
        if self.is_hq_voucher:
            self.discount_type = FIXED_AMOUNT

    @api.multi
    def action_view_voucher(self):
        action = self.env.ref('br_discount.action_view_voucher').read()[0]
        action['context'] = {
            'default_code': self.code
        }
        return action

    @api.onchange('is_voucher')
    @api.one
    def onchange_is_voucher(self):
        if self.is_voucher:
            self.user_quota_lines = None

    @api.one
    def write(self, vals):
        is_voucher = vals['is_voucher'] if 'is_voucher' in vals else self.is_voucher
        is_group_user = False
        quota_type = vals['quota_type'] if 'quota_type' in vals else self.quota_type
        user_quota_type = vals['user_quota_type'] if 'user_quota_type' in vals else self.user_quota_type

        if is_voucher and quota_type:
            raise ValidationError("Cannot apply voucher with outlet quota in one discount. Please select 1 option only")
        if user_quota_type and quota_type:
            raise ValidationError(
                "Cannot apply both outlet and user quota in one discount. Please select 1 option only")

        if 'user_quota_lines' in vals and vals['user_quota_lines']:
            if vals['user_quota_lines'][0] and vals['user_quota_lines'][0][2] and len(
                    vals['user_quota_lines'][0][2]) > 0:
                is_group_user = True
        else:
            if self.user_quota_lines:
                is_group_user = True
        if is_voucher and is_group_user:
            raise ValidationError("Cannot apply both Voucher and User for one promotion")

        if ('promotion_category_id' in vals and vals['promotion_category_id']) or (
                'type_promotion' in vals and vals['type_promotion']):
            new_code = ''
            # sq = self.env['ir.sequence'].next_by_code('br.bundle.promotion')
            sq = self.code_sequence
            if 'promotion_category_id' in vals and vals['promotion_category_id']:
                # get parent location
                categ = self.env['br.promotion.category'].browse(vals['promotion_category_id'])
            else:
                categ = self.promotion_category_id
            parent_categ = categ.parent_id
            categ_code = [categ.code]
            while parent_categ:
                if parent_categ.code:
                    categ_code.append(parent_categ.code)
                parent_categ = parent_categ.parent_id

            for item in reversed(categ_code):
                new_code += item
            new_code += sq
            vals.update({'code': new_code})

        return super(BrBundlePromotion, self).write(vals)

    @api.model
    def create(self, vals):
        if 'is_voucher' in vals and vals['is_voucher'] and 'quota_type' in vals and vals['quota_type']:
            raise ValidationError("Cannot apply voucher with outlet quota in one discount. Please select 1 option only")
        if 'user_quota_type' in vals and vals['user_quota_type'] and 'quota_type' in vals and vals['quota_type']:
            raise ValidationError(
                "Cannot apply both outlet and user quota in one discount. Please select 1 option only")
        ctx = {'force_company': self.env.user.company_id.id}
        sq = self.env['ir.sequence'].with_context(ctx).next_by_code('br.bundle.promotion') or ''
        # get parent location
        categ = self.env['br.promotion.category'].browse(vals['promotion_category_id'])
        parent_categ = categ.parent_id
        arr_code = [categ.code]
        categ_code = ''
        while parent_categ:
            if parent_categ.code:
                arr_code.append(parent_categ.code)

            parent_categ = parent_categ.parent_id
        # get parent location
        for item in reversed(arr_code):
            categ_code += item
        # get parent location
        vals['code_sequence'] = sq
        vals['code'] = categ_code + sq
        return super(BrBundlePromotion, self).create(vals)

    @openerp.api.depends('image')
    def _compute_images(self):
        for rec in self:
            rec.image_medium = tools.image_resize_image_medium(rec.image)
            rec.image_small = tools.image_resize_image_small(rec.image)

    @api.multi
    def delete_all_voucher(self):
        self.env['br.config.voucher'].search([('promotion_id', '=', self.id), ('status', '!=', 'redeemed')]).unlink()
        return True

    @api.multi
    def create_voucher(self):
        model_data = self.env['ir.model.data']
        model_data_ids = model_data.search(
            [('model', '=', 'ir.ui.view'), ('name', '=', 'br_promotion_voucher_gen_view')])
        ctx = dict(
            default_promotion_id=self.id,
            default_start_date=self.start_date,
            default_end_date=self.end_date,
        )
        return {
            'name': 'Voucher Gen',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'br.promotion.voucher.gen',
            'view_id': model_data_ids.res_id,
            'context': ctx,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    @api.multi
    def backup_many2many(self):
        # create cursor
        cr = self.env.cr
        # get all relation data
        cr.execute("SELECT * FROM br_config_voucher_pos_order_rel")
        all_voucher_order = cr.dictfetchall()
        # get all voucher id
        cr.execute("SELECT id FROM br_config_voucher")
        all_voucher = cr.fetchall()
        # get all order id
        cr.execute("SELECT id FROM pos_order")
        all_order = cr.fetchall()
        # change list of tuple become list of int
        list_voucher_id = []
        for voucher in all_voucher:
            list_voucher_id.append(voucher[0])
        list_order_id = []
        for order in all_order:
            list_order_id.append(order[0])
        # check and backup
        for vopo in all_voucher_order:
            if vopo['br_config_voucher_id'] in list_voucher_id and vopo['pos_order_id'] in list_order_id:
                voucher_obj = self.env['br.config.voucher'].browse(vopo['br_config_voucher_id'])
                voucher_obj.order_id = self.env['pos.order'].browse(vopo['pos_order_id'])
        return True

    @api.multi
    def export_voucher(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_voucher?model=br.bundle.promotion&id=%s' % (self.id),
            'target': 'self',
        }

    @api.multi
    def select_outlets(self):
        model_data = self.env['ir.model.data']
        model_data_ids = model_data.search(
            [('model', '=', 'ir.ui.view'), ('name', '=', 'br_tmp_select_outlets_form')])
        ctx = dict(
            default_promotion_id=self.id,
            default_start_date=self.start_date,
            default_end_date=self.end_date,
        )
        ls_outlet = self.env['br_multi_outlet.outlet'].search([])
        ls_tmp = self.env['br.tmp.select.outlets'].search([], limit=1)
        ls_tmp.unlink()
        vals = []
        for item in ls_outlet:
            vals.append([0, 0, {'outlet_id': item.id}])
        res_id = self.env['br.tmp.select.outlets'].create({'outlet_line_ids': vals, 'promotion_id': self.id})
        return {
            'name': 'Select Outlets',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'br.tmp.select.outlets',
            'view_id': model_data_ids.res_id,
            'context': ctx,
            'target': 'new',
            'res_id': res_id.id,
            'type': 'ir.actions.act_window'
        }

    @api.multi
    def voucher_enddate(self):
        model_data = self.env['ir.model.data']
        model_data_ids = model_data.search(
            [('model', '=', 'ir.ui.view'), ('name', '=', 'br_promotion_voucher_enddate_view')])
        ctx = dict(
            default_promotion_id=self.id,
            default_start_date=self.start_date,
            default_end_date=self.end_date,
        )
        return {
            'name': 'Modify Vouchers',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'br.promotion.voucher.enddate',
            'view_id': model_data_ids.res_id,
            'context': ctx,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    @api.one
    @api.onchange('is_all_outlet')
    def onchange_is_all_outlet(self):
        if not self.is_all_outlet:
            self.outlet_ids = []

    @api.model
    def get_promotion_line(self, promotion_id):
        result = {}
        promotion_lines = []
        promotion = self.browse(promotion_id)
        # 1: bill discount, 2: product discount, 3: bundle discount
        promo_type = promotion.type_promotion
        if promo_type == 2:
            promotion_lines = promotion.product_promotion_ids
        elif promotion.type_promotion == 3:
            promotion_lines = promotion.bundle_promotion_ids
        for item in promotion_lines:
            result[item.id] = {'min_quantity': item.min_quantity}
        return result


class br_pos_order_line(models.Model):
    _inherit = 'pos.order.line'

    promotion_ids = fields.Many2many('br.bundle.promotion', 'pos_order_line_promotion_default_rel',
                                     'pos_order_line_id', 'promotion_id', string='Promotions')


class br_select_outlets(models.Model):
    _name = 'br.tmp.select.outlets'

    promotion_id = fields.Many2one('br.bundle.promotion')
    outlet_ids = fields.Many2many('br_multi_outlet.outlet', 'select_outlets_multi_outlet_rel', 'select_outlets_id',
                                  'multi_outlet_id', string='Outlets')

    @api.one
    def popup_select_outlet(self):
        promotion = self.promotion_id
        old_outlet_quota_lines = promotion.outlet_quota_lines
        for quota in old_outlet_quota_lines:
            quota.unlink()
        new_quota_lines = []
        for item in self.outlet_ids:
            new_quota_lines.append([0, 0, {'outlet_id': item.id}])

        if self.env.user.id != SUPERUSER_ID:
            all_outlets = self.env['br_multi_outlet.outlet'].search([('company_id', '=', self.env.user.company_id.id)])
        else:
            all_outlets = self.env['br_multi_outlet.outlet'].search([])

        if len(new_quota_lines) == len(all_outlets):
            promotion.write({'outlet_quota_lines': new_quota_lines, 'is_all_outlet': True})
        else:
            promotion.write({'outlet_quota_lines': new_quota_lines, 'is_all_outlet': False})
