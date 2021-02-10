from openerp import models, fields, api, _
from common import UOM_TYPE


class StockRequest(models.Model):
    _name = 'br.stock.request.form'
    _order = 'name'

    name = fields.Char(string="Name", required=True, copy=False)
    product_categ_ids = fields.Many2many(comodel_name='product.category', string="Product Category(s)")
    from_date = fields.Datetime(string="Start Date")
    to_date = fields.Datetime(string="To Date")
    line_ids = fields.One2many(string="Lines", comodel_name='br.stock.request.form.line', inverse_name='request_id', copy=True)

    warehouse_ids = fields.Many2many(string="Source Warehouse(s)", comodel_name='stock.warehouse')
    warehouse_dest_ids = fields.Many2many(string="Destination Warehouse(s)",
                                          rel='br_stock_request_form_stock_warehouse_dest_rel',
                                          comodel_name='stock.warehouse')
    len_warehouse_ids = fields.Integer(string="Src Warehouse Count", compute="_get_warehouse_length", store=True)
    len_warehouse_dest_ids = fields.Integer(string="Dest Warehouse Count", compute="_get_warehouse_length", store=True)
    line_ids_related = fields.One2many(string="Lines Related", comodel_name='br.stock.request.form.line', compute='_get_line_ids_related')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name of the Request Form must be unique!')
    ]

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if 'name' not in default:
            form = self.browse(cr, uid, id, context=context)
            default['name'] = _("%s (copy)") % (form.name)
        return super(StockRequest, self).copy(cr, uid, id, default=default, context=context)

    @api.depends('line_ids')
    def _get_line_ids_related(self):
        self.line_ids_related = self.line_ids.filtered(lambda x: x.product_id.active)

    @api.multi
    @api.depends('warehouse_dest_ids', 'warehouse_ids')
    def _get_warehouse_length(self):
        for form in self:
            form.len_warehouse_ids = len(form.warehouse_ids)
            form.len_warehouse_dest_ids = len(form.warehouse_dest_ids)

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
                uom_type = 'standard'
                sellers = p.seller_ids
                if sellers:
                    for s in sellers:
                        if s.uom_ids:
                            uom_type = 'distribution'
                            break
                vals.append((0, 0, {
                    'product_id': p.id,
                    'uom_type': uom_type,
                    'auto_added': True
                }))
        if vals:
            self.line_ids = vals


class StockRequestLine(models.Model):
    _name = 'br.stock.request.form.line'

    product_id = fields.Many2one(comodel_name='product.product', string="Product")
    uom_type = fields.Selection(
        selection=UOM_TYPE,
        string="UOM Type", default="standard")
    request_id = fields.Many2one(comodel_name='br.stock.request.form')
    auto_added = fields.Boolean(default=False)
