from openerp import models, fields, api, SUPERUSER_ID, _
import br_model
from lxml import etree
from openerp.osv.orm import setup_modifiers


class StockWarehouse(br_model.BrModel):
    _inherit = 'stock.warehouse'

    user_ids = fields.Many2many(comodel_name='res.users', string=_("Users"))

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'stock.warehouse':
            domain.append(('id', 'in', [x.id for x in user.warehouse_ids]))
        return domain

    @api.model
    def create(self, vals):
        users = [self.env.uid]
        if 'user_ids' in vals and vals['user_ids']:
            users += vals['user_ids'][0][2]
        vals.update(user_ids=[[6, 0, list(set(users))]])
        return super(StockWarehouse, self).create(vals)


class StockPickingType(br_model.BrModel):
    _inherit = 'stock.picking.type'

    @api.model
    def _get_domain(self, user, domain):
        domain.extend([
            '|',
            ('warehouse_id.user_ids', 'in', [user.id]),
            ('warehouse_id', '=', None),
            '|',
            ('default_location_src_id', 'in', user.location_ids.ids),
            ('default_location_dest_id', 'in', user.location_ids.ids),
        ])
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockPickingType, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        location_field_names = ['default_location_src_id', 'default_location_dest_id']
        for f_name in location_field_names:
            if doc.xpath("//field[@name='%s']" % f_name):
                node = doc.xpath("//field[@name='%s']" % f_name)[0]
                node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.location_ids.ids))
                setup_modifiers(node, result['fields'][f_name])
        result['arch'] = etree.tostring(doc)
        return result


class BrStockInventory(br_model.BrModel):
    _inherit = 'stock.inventory'

    _defaults = {
        'location_id': False
    }

    @api.model
    def _get_domain(self, user, domain):
        domain.append(['location_id', 'child_of', [x.view_location_id.id for x in user.warehouse_ids]])
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(BrStockInventory, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        if doc.xpath("//field[@name='location_id']"):
            node = doc.xpath("//field[@name='location_id']")[0]
            domain = []
            if node.attrib and 'domain' in node.attrib:
                domain = eval(node.attrib['domain'])
            domain.append(('id', 'in', self.env.user.location_ids.ids))
            node.set('domain', str(domain))
            setup_modifiers(node, result['fields']['location_id'])
        result['arch'] = etree.tostring(doc)
        return result


class StockMove(br_model.BrModel):
    _inherit = 'stock.move'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'stock.move':
            location_ids = user.location_ids.ids
            domain.extend([
                '|',
                ('location_id', 'in', location_ids),
                ('location_dest_id', 'in', location_ids),
                ('picking_type_id', 'in', user.picking_type_ids.ids)
            ])
        return domain


class StockQuant(br_model.BrModel):
    _inherit = 'stock.quant'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'stock.quant' or self._get_active_model() == 'stock.production.lot':
            domain.extend([
                ('location_id', 'in', user.location_ids.ids)
            ])
        return domain


class StockPicking(br_model.BrModel):
    _inherit = 'stock.picking'

    @api.model
    def _get_domain(self, user, domain):
        wh_loc_ids = [x.view_location_id.id for x in user.warehouse_ids]
        domain.extend(['|', ['location_id', 'child_of', wh_loc_ids], ['location_dest_id', 'child_of', wh_loc_ids]])
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockPicking, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        location_field_names = ['location_id', 'location_dest_id']
        for f_name in location_field_names:
            if doc.xpath("//field[@name='%s']" % f_name):
                node = doc.xpath("//field[@name='%s']" % f_name)[0]
                node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.location_ids.filtered(lambda r: r.usage != 'transit').ids))
                setup_modifiers(node, result['fields'][f_name])
        result['arch'] = etree.tostring(doc)
        return result


class StockLocation(br_model.BrModel):
    _inherit = 'stock.location'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockLocation, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        if doc.xpath("//field[@name='location_id']"):
            node = doc.xpath("//field[@name='location_id']")[0]
            node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.location_ids.ids))
            setup_modifiers(node, result['fields']['location_id'])
        result['arch'] = etree.tostring(doc)
        return result

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'stock.location' and not self.env.context.get('user_filter', False):
            domain.extend([
                ('id', 'in', user.location_ids.ids)
            ])
        return domain


class StockWarehouseOrderPoint(br_model.BrModel):
    _inherit = 'stock.warehouse.orderpoint'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'stock.warehouse.orderpoint':
            domain.extend([
                ('location_id', 'in', user.location_ids.ids),
                ('warehouse_id', 'in', user.warehouse_ids.ids),
            ])
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockWarehouseOrderPoint, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        if doc.xpath("//field[@name='location_id']"):
            node = doc.xpath("//field[@name='location_id']")[0]
            node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.location_ids.ids))
            setup_modifiers(node, result['fields']['location_id'])
        if doc.xpath("//field[@name='warehouse_id']"):
            node = doc.xpath("//field[@name='warehouse_id']")[0]
            node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.warehouse_ids.ids))
            setup_modifiers(node, result['fields']['warehouse_id'])
        result['arch'] = etree.tostring(doc)
        return result


class StockQuantPackage(br_model.BrModel):
    _inherit = 'stock.quant.package'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'stock.quant.package':
            domain.extend([
                ('location_id', 'in', user.location_ids.ids)
            ])
        return domain


class ProcurementOrder(br_model.BrModel):
    _inherit = 'procurement.order'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'procurement.order':
            domain.extend([
                ('location_id', 'in', user.location_ids.ids),
                ('warehouse_id', 'in', user.warehouse_ids.ids)
            ])
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(ProcurementOrder, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        if doc.xpath("//field[@name='location_id']"):
            node = doc.xpath("//field[@name='location_id']")[0]
            node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.location_ids.ids))
            setup_modifiers(node, result['fields']['location_id'])
        result['arch'] = etree.tostring(doc)
        return result


class StockRequestTransfer(br_model.BrModel):
    _inherit = 'br.stock.request.transfer'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'br.stock.request.transfer':
            domain.extend([
                '|',
                ('warehouse_id', 'in', user.warehouse_ids.ids),
                ('dest_warehouse_id', 'in', user.warehouse_ids.ids),
            ])
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockRequestTransfer, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        if doc.xpath("//field[@name='dest_warehouse_id']"):
            node = doc.xpath("//field[@name='dest_warehouse_id']")[0]
            domain = []
            if node.attrib and 'domain' in node.attrib:
                domain = eval(node.attrib['domain'])
            domain.append(('id', 'in', self.env.user.warehouse_ids.ids))
            node.set('domain', str(domain))
            setup_modifiers(node, result['fields']['dest_warehouse_id'])
        result['arch'] = etree.tostring(doc)
        return result
