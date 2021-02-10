from openerp import models, api, fields, _
from openerp.osv import fields as Ofields
from openerp.exceptions import ValidationError
from lxml import etree
from openerp.osv.orm import setup_modifiers


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    _columns = {
        # Just want to change label when tracking is lot, should override in __init__ ?
        'tracking': Ofields.selection(selection=[('serial', 'By Unique Serial Number'), ('lot', 'By Expiry Date'), ('none', 'No Tracking')], string="Tracking", required=True),
    }

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(ProductTemplate, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        # Hide "Update qty onhand" button
        if doc.xpath("//header/button[2]"):
            node = doc.xpath("//header/button[2]")[0]
            node.set('invisible', '1')
            setup_modifiers(node, result)
        result['arch'] = etree.tostring(doc)
        return result

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(ProductProduct, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        # Hide "Update qty onhand" button
        if doc.xpath("//header/button[2]"):
            node = doc.xpath("//header/button[2]")[0]
            node.set('invisible', '1')
            setup_modifiers(node, result)
        result['arch'] = etree.tostring(doc)
        return result

    def _check_need_tracking(self, *args):
        fields = [
            'location_id',
            'location_dest_id'
        ]
        locations = self.env['stock.location']
        for ob in args:
            for f in fields:
                location_id = getattr(ob, f, None)
                if location_id:
                    locations |= location_id
        check = self.tracking != 'none' and any([x.manage_expirydate for x in locations])
        return check


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    active = fields.Boolean(string="Active", default=True)
    tracking = fields.Selection(selection=[('serial', 'By Unique Serial Number'), ('lot', 'By Expiry Date'), ('none', 'No Tracking')], related='product_id.tracking', readonly=True)

    _defaults = {
        'name': '/'
    }

    @api.constrains('name')
    def _check_unique_name(self):
        if self.tracking == 'lot':
            res = self.search(
                [('id', '!=', self.id),
                 ('name', '=', self.name),
                 ('br_supplier_id', '=', self.br_supplier_id.id),
                 ('product_id', '=', self.product_id.id),
                 ]
            )
            if res:
                raise ValidationError("This serial number of this supplier is already created!")

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == '/':
            vals.update(name=vals['removal_date'].split(' ')[0] or '/')
        return super(StockProductionLot, self).create(vals)

    @api.multi
    def write(self, vals):
        if 'removal_date' in vals:
            vals.update(name=vals['removal_date'].split(' ')[0] or '/')
        return super(StockProductionLot, self).write(vals)
