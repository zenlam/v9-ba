# -*- coding: utf-8 -*-

from openerp import api, fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        if 'from_wizard' in self._context:
            if self._context.get('from_wizard'):
                categs = self.env['product.category']
                parents = self.search([('parent_id', '=', False)], order='id')
                if parents:
                    categs += self.search([
                        ('parent_id', 'in', parents.ids)], order='id')
                # categs |= parents
                domain += [('id', 'in', categs.ids)]
        elif 'parent_categ_ids' in self._context:
            categ_ids = []
            if self._context.get('parent_categ_ids'):
                categ_ids = self._context['parent_categ_ids'][0][2]
            if not categ_ids:
                categs = self.env['product.category']
                parents = self.search([('parent_id', '=', False)], order='id')
                if parents:
                    categs += self.search([
                        ('parent_id', 'in', parents.ids)], order='id')
                    categ_ids = categs.ids
            domain += [('id', 'in', categ_ids)]
        return super(ProductCategory, self).name_search(
            name, args=domain+args, operator=operator, limit=limit)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        domain = []
        categ_ids = self._context.get('product_categ_ids', [])
        if categ_ids and categ_ids[0][2]:
            products = self.search([('categ_id', 'child_of', categ_ids[0][2])], order='id')
            domain += [('id', 'in', products.ids)]
        return super(ProductProduct, self).name_search(
            name, args=domain+args, operator=operator, limit=limit)


class InventoryCategUomType(models.Model):
    _name = 'inventory.categ.uom.type'

    uom_categ_id = fields.Many2one('product.category', string='Category')
    uom_type = fields.Selection([
                    ('standard', 'Standard'),
                    ('purchase', 'Purchase UoM'),
                    ('distribution', 'Distribution'),
                    ('storage', 'Storage'),
                    ], string='UoM Type')
    parent_categ_id = fields.Many2one('product.category', string='Parent Category')
