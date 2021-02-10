from openerp import api, fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.multi
    def write(self, vals):
        children = self.env['product.category'].search([('id', 'child_of', self.id)])
        res = super(ProductCategory, self).write(vals)
        if 'name' in vals:
            self.change_child_name(children)
        elif 'parent_id' in vals:
            self.change_child_name(children)
        return res

    @api.multi
    def change_child_name(self, children):
        if children:
            for c in children:
                c.complete_name = c.name_get()