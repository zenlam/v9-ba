from openerp import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    uom_id = fields.Many2one('product.uom', copy=False)
    uom_po_id = fields.Many2one('product.uom', copy=False)
    uom_name = fields.Char(string='Standard UoM')

    @api.model
    def create(self, vals):
        if self._context.get('load_menu_name', False):
            uom_id = self.env["product.uom"].search([], limit=1, order='id')[0]
            vals.update({'uom_id': uom_id.id, 'uom_name': uom_id.name})
        else:
            # auto create uom, uom-cate
            uom_cate = self.env['product.uom.categ'].create({'name': vals.get('name')})
            uom = self.env['product.uom'].create(
                {'name': vals.get('uom_name'), 'category_id': uom_cate.id, 'uom_type': 'reference'})
            vals.update({'uom_id': uom.id, 'uom_po_id': uom.id})
        return super(ProductTemplate, self).create(vals)

    @api.multi
    def write(self, vals):
        # auto update uom when user edit uom_name
        res = super(ProductTemplate, self).write(vals)
        if vals.get('uom_name', False):
            for product in self:
                product.uom_id.name = vals.get('uom_name')
        return res

    @api.model
    def update_uom_name(self):
        list_product = self.search([('uom_name', '=', False)])
        for product in list_product:
            product.uom_name = product.uom_id.name
