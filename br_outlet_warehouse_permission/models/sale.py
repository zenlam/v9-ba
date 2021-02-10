from openerp import fields, models, api, _
import br_model
from lxml import etree
from openerp.osv.orm import setup_modifiers


class SaleOrder(br_model.BrModel):
    _inherit = 'sale.order'

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'sale.order':
            domain.extend([
                ('warehouse_id', 'in', user.warehouse_ids.ids)
            ])
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(SaleOrder, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        if doc.xpath("//field[@name='warehouse_id']"):
            node = doc.xpath("//field[@name='warehouse_id']")[0]
            node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.warehouse_ids.ids))
            setup_modifiers(node, result['fields']['warehouse_id'])
        result['arch'] = etree.tostring(doc)
        return result