from openerp import models, fields, api, _
import sets


class PosOrder(models.Model):
    _inherit = 'pos.order'
    sale_voucher_ids = fields.One2many(string="Sale Voucher", comodel_name='pos.order.sale.voucher.detail',
                                       inverse_name='order_id')

    def _payment_fields(self, cr, uid, ui_paymentline, context=None):
        res = super(PosOrder, self)._payment_fields(cr, uid, ui_paymentline, context=context)
        res.update(voucher_id=ui_paymentline['voucher_id'],unredeem_value=ui_paymentline.get('unredeem_value', 0))
        return res

    @api.model
    def add_payment(self, order_id, data):
        """ Update voucher_id for statement line"""
        statement_id = super(PosOrder, self).add_payment(order_id, data)
        if 'voucher_id' in data:
            statement_lines = self.env['account.bank.statement.line'].search([('statement_id', '=', statement_id)], order='id')
            # Lastest statement line is the current line
            statement_lines[-1].write({'voucher_id': data['voucher_id'], 'unredeem_value': data['unredeem_value']})
        return statement_id

    @api.model
    def _process_order(self, ui_order):
        # Update voucher id for statement line because currently voucher isn't wrote as a model in front end
        # which is silly in my opinion ...
        for stm in ui_order['statement_ids']:
            if 'voucher_code' in stm[2]:
                voucher = self.env['br.config.voucher'].search([('voucher_validation_code', '=', stm[2]['voucher_code'])], limit=1)
                stm[2]['voucher_id'] = voucher.id if voucher else False
        order_id = super(PosOrder, self)._process_order(ui_order)
        order = self.env['pos.order'].browse(order_id)
        sale_vouchers = self.get_sale_voucher(order)
        if sale_vouchers:
            order.write({'sale_voucher_ids': [(0, 0, v) for v in sale_vouchers]})
        return order_id

    def get_sale_voucher(self, order):
        sale_vouchers = []
        tip_product = order.session_id.config_id.tip_product_id
        if tip_product.property_account_income_id.id:
            income_account = tip_product.property_account_income_id.id
        elif tip_product.categ_id.property_account_income_categ_id.id:
            income_account = tip_product.categ_id.property_account_income_categ_id.id
        else:
            income_account = False
        outlet_analytic_account_id = order.outlet_id and order.outlet_id.analytic_account_id and order.outlet_id.analytic_account_id.id or False
        # All vouchers from order
        # Get tax_ids from first order line ...(find a cleaner way)
        taxes = order.lines[0].tax_ids_after_fiscal_position
        tax_ids = taxes.ids if taxes else []
        tax_account_id = taxes[0].account_id.id if taxes else False
        # Get product voucher from payment
        for payment in order.statement_ids:
            voucher = payment.voucher_id
            promotion = voucher.promotion_id
            promotion_type = 'cash' if promotion.type_promotion == 1 else 'product'
            # Group Menu name with same voucher
            if promotion.is_hq_voucher and promotion.analytic_account_id:
                sale_vouchers.append({
                    'journal_id': payment.journal_id.id,
                    'voucher_id': payment.voucher_id.id,
                    'analytic_account_id': promotion.analytic_account_id.id,
                    'outlet_analytic_account_id': outlet_analytic_account_id,
                    'tax_account_id': tax_account_id,
                    'tax_ids': [(6, 0, tax_ids)],
                    'value': payment.amount - payment.unredeem_value,
                    'unredeem_income_account_id': income_account,
                    'unredeem_value': payment.unredeem_value,
                    'voucher_type': promotion_type
                })
                # Should not subtract unredeem value for all
        return sale_vouchers


class PosOrderLineMaster(models.Model):
    _inherit = 'br.pos.order.line.master'

    voucher_id = fields.Many2one(string="Voucher", comodel_name='br.config.voucher', ondelete='restrict')


class PosOrderline(models.Model):
    _inherit = 'pos.order.line'

    @api.model
    def _order_master_fields(self, line):
        res = super(PosOrderline, self)._order_master_fields(line)
        if res and 'voucher' in line[2] and line[2]['voucher']:
            product_discount = 2
            for voucher_code in line[2]['voucher']:
                voucher = self.env['br.config.voucher'].search([('voucher_validation_code', '=', voucher_code)], limit=1)
                # Tag product discount to menu line
                if voucher and voucher.promotion_id.type_promotion == product_discount:
                    line[2]['voucher_id'] = voucher.id
                    break
        return res


class PosOrderSaleVoucherDetail(models.Model):
    # Store the sale voucher data for future posting
    _name = 'pos.order.sale.voucher.detail'

    VOUCHER_TYPE = [('product', 'Product Voucher'), ('cash', 'Cash Voucher')]

    order_id = fields.Many2one(comodel_name='pos.order', string="Pos Order")
    voucher_id = fields.Many2one(comodel_name='br.config.voucher', string="Voucher")
    analytic_account_id = fields.Many2one(comodel_name='account.analytic.account', string="Analytic Account")
    outlet_analytic_account_id = fields.Many2one(comodel_name='account.analytic.account', string="Outlet Analytic Account")
    tax_ids = fields.Many2many(comodel_name='account.tax', string="Tax(es)")
    value = fields.Float(string="Value", digits=(18, 2), default=0)
    unredeem_value = fields.Float(string="Unredeem Value", digits=(18, 2), default=0)
    voucher_type = fields.Selection(selection=VOUCHER_TYPE)
    tax_account_id = fields.Many2one(comodel_name='account.account', string="Tax Account")
    unredeem_income_account_id = fields.Many2one(comodel_name='account.account', string="Unredeem Income Account")
    journal_id = fields.Many2one(comodel_name='account.journal', string="Account Journal")


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    voucher_id = fields.Many2one(comodel_name='br.config.voucher', string="Voucher")
    unredeem_value = fields.Float(string="Unredeem Value", digits=(18, 2), default=0)


class barcode_rule(models.Model):
    _inherit = 'barcode.rule'

    def _get_type_selection(self):
        types = sets.Set(super(barcode_rule,self)._get_type_selection())
        types.update([
            ('discount_voucher', _('Voucher Discount'))
        ])
        return list(types)
