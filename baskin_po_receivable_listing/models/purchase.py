# -*- coding: utf-8 -*-

from openerp import api, fields, models, _, SUPERUSER_ID


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('product_qty', 'qty_invoiced', 'qty_received')
    @api.multi
    def _get_qty_status(self):
        for line in self:
            if line.product_qty == line.qty_invoiced == line.qty_received:
                line.qty_status = 'full_receive_full_billed'
            elif line.product_qty == line.qty_received and line.qty_invoiced < line.qty_received:
                line.qty_status = 'full_receive_partially_billed'
            elif line.product_qty > line.qty_received and line.qty_invoiced < line.qty_received:
                line.qty_status = 'partially_receive_partially_billed'
            else:
                line.qty_status = 'other'

    @api.depends('product_qty', 'qty_invoiced')
    @api.multi
    def _get_cons_qty_status(self):
        for line in self:
            if line.product_qty == line.qty_invoiced:
                line.cons_qty_status = 'full_billed'
            elif line.product_qty > line.qty_invoiced:
                line.cons_qty_status = 'partially_billed'
            else:
                line.cons_qty_status = 'other'

    @api.depends('product_qty', 'qty_invoiced', 'qty_received')
    @api.multi
    def _check_qty(self):
        for line in self:
            if line.qty_received > line.product_qty:
                line.is_receive_gt_order = True
            if line.qty_invoiced > line.qty_received:
                line.is_bill_gt_receive = True

    po_ref = fields.Char(related='order_id.name', string='Ref', store=True)
    state = fields.Selection(related='order_id.state', store=True)
    product_type = fields.Selection(related='product_id.type', string="Product Type", store=True)
    qty_status = fields.Selection([('full_receive_full_billed', 'Fully Received Fully Billed'),
                                   ('full_receive_partially_billed', 'Fully Received Partially Billed'),
                                   ('partially_receive_partially_billed', 'Partially Received Partially Billed'),
                                   ('other', 'Other')],
                                  compute='_get_qty_status', store=True, string="Qty Status")
    cons_qty_status = fields.Selection([('full_billed', 'Fully Billed'),
                                        ('partially_billed', 'Partially Billed'),
                                        ('other', 'Other')],
                                       compute='_get_cons_qty_status', store=True, string="Cons Qty Status")
    account_id = fields.Many2one('account.account', string='Account',
                                 domain=[('deprecated', '=', False)],
                                 help="Expense account related to the selected product.")
    is_receive_gt_order = fields.Boolean(string='Is Received Qty Greater Than Ordered Qty', default=False,
                                         compute='_check_qty', store=True)
    is_bill_gt_receive = fields.Boolean(string='Is Billed Qty Greater Than Received Qty', default=False,
                                        compute='_check_qty', store=True)

    @api.model
    def get_purchase_line_account(self, product):
        accounts = product.product_tmpl_id.get_product_accounts()
        # note : confirm from "mitesh prajapati" that for purchase always select expense account of product
        return accounts['expense']

    @api.onchange('product_id')
    def onchange_product_id(self):
        res = super(PurchaseOrderLine, self).onchange_product_id()
        if self.product_id:
            account = self.get_purchase_line_account(self.product_id)
            if account:
                self.account_id = account.id
        return res


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.multi
    def _get_product_accounts(self):
        res = super(ProductTemplate, self)._get_product_accounts()
        res.update(
            income=self.property_account_income_id or self.categ_id.property_account_income_categ_id,
            expense=self.asset_category_id.br_asset_account or self.categ_id.property_account_expense_categ_id
        )
        return res