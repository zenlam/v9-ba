from datetime import datetime, timedelta

from common import STOCK_COUNT_TYPE, UOM_TYPE, GROUP_TYPE
from openerp import fields, models, api, _
from openerp.exceptions import ValidationError


class StockInventoryTemplate(models.Model):
    _name = 'stock.inventory.template'

    name = fields.Char(string="Template Name", required=1)
    filter = fields.Selection(string="Inventory Of", selection=[('none', 'All'), ('partial', 'Selected products')],
                              default='none')
    started_by = fields.Many2one(string="Last Edited By", comodel_name='res.users')
    type = fields.Selection(string="Stock Count Type",
                            selection=STOCK_COUNT_TYPE, default='official')
    line_ids = fields.One2many(string="Template Lines", comodel_name='stock.inventory.template.line',
                               inverse_name='template_id', copy=True)
    warehouse_ids = fields.Many2many(string="Warehouse(s)", comodel_name='stock.warehouse')
    warehouse_ids_len = fields.Integer(string="Warehouse Length", compute="_get_warehouse_ids_len", store=True)
    line_ids_related = fields.One2many(string="Template Lines", comodel_name='stock.inventory.template.line',
                                       related="line_ids", copy=True)
    active = fields.Boolean(_("Active"), default=True)

    @api.model
    def create(self, vals):
        if 'line_ids_related' in vals and 'line_ids' in vals and not vals['line_ids_related']:
            del vals['line_ids_related']
        return super(StockInventoryTemplate, self).create(vals)

    @api.multi
    def action_prepare_inventory(self):
        inventory_obj = self.env['stock.inventory']
        # warehouse_obj = self.env['stock.warehouse']
        for template in self:
            warehouses = self.warehouse_ids  # if self.warehouse_ids else warehouse_obj.search([])
            for wh in warehouses:
                inventory = inventory_obj.create(template._prepare_inventory_value(wh))
                inventory.prepare_inventory()

    def _prepare_inventory_value(self, warehouse):
        inventory_date = self.env.context.get('inventory_date', None) or datetime.now()
        accounting_date = inventory_date + timedelta(hours=8)
        location = warehouse.lot_stock_id
        return {
            'name': "%s - %s - %s" % (warehouse.name, self.name, accounting_date.strftime('%y%m%d%')),
            'location_id': location.id,
            'account_analytic_id': location.get_analytic_account(),
            'stock_count_type': self.type,
            'template_id': self.id,
            'date': inventory_date,
            'filter': self.filter,
            'accounting_date': accounting_date.date()
        }

    @api.depends('warehouse_ids')
    @api.multi
    def _get_warehouse_ids_len(self):
        for t in self:
            t.warehouse_ids_len = len(t.warehouse_ids)

    @api.constrains('line_ids')
    def _check_line_ids(self):
        existed_product = []
        existed_group_name = []
        for line in self.line_ids:
            if line.group_name not in existed_group_name:
                existed_group_name.append(line.group_name)
            else:
                raise ValidationError(_("Can't have duplicate group name !"))
            line_products = line.all_product_ids
            if line_products:
                for p in line_products:
                    if p.id in existed_product:
                        raise ValidationError(_("There is duplicate product/category%s !" % (
                            " in group %s" % line.group_name if line.group_name else "")))
                existed_product.extend(line_products.ids)
            else:
                raise ValidationError(_("You must config either Product or Product Category for %s" % line.group_name))

    @api.onchange('type')
    @api.multi
    def onchange_type(self):
        for t in self:
            for l in t.line_ids:
                l.template_type = t.type


class StockInventoryTemplateLine(models.Model):
    _name = 'stock.inventory.template.line'

    template_id = fields.Many2one(comodel_name='stock.inventory.template', string="Template", ondelete='restrict')
    product_ids = fields.Many2many(string="Product(s)", comodel_name='product.product')
    group_name = fields.Char(string="Group Name")
    product_categ_ids = fields.Many2many(string="Category(s)", comodel_name='product.category')
    uom_type = fields.Selection(string="Loss/Gain UOM", selection=UOM_TYPE, default='distribution')
    is_total_count = fields.Boolean(string="Count By Total", default=False)
    all_product_ids = fields.Many2many(comodel_name='product.product', string="All Products",
                                       compute="_get_all_products")
    group_type = fields.Selection(selection=GROUP_TYPE, string='Group Type', default='others')
    ref_product_id = fields.Many2one(string="Reference Product", comodel_name='product.product')
    template_type = fields.Selection(selection=STOCK_COUNT_TYPE)

    @api.depends('product_ids', 'product_categ_ids')
    @api.multi
    def _get_all_products(self):
        for line in self:
            products = self.env['product.product']
            for product in line.product_ids:
                products |= product
            for categ in line.product_categ_ids:
                products |= self.env['product.product'].search([('categ_id', 'child_of', categ.id)])
            line.all_product_ids = products


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        self._set_domain(args)
        return super(ProductProduct, self).search(args, offset=offset, limit=limit, order=order, count=count)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        self._set_domain(args)
        return super(ProductProduct, self).name_search(name, args=args, operator=operator, limit=limit)

    def _set_domain(self, args):
        """Get available product lot in stock by location, product and vendor"""
        if self.env.context.get('allowed_products', False):
            # allowed_products is computed many2many field
            ids = self.env.context.get('allowed_products')[0][2]
            for arg in args:
                field = arg[0]
                if field == 'id':
                    filter_ids = arg[2]
                    if isinstance(filter_ids, list):
                        filter_ids.extend(ids)
                    break
            else:
                args.extend([(u'id', u'in', ids)])
