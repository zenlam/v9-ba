from openerp import models, fields, api, SUPERUSER_ID, _
from lxml import etree
from openerp.osv.orm import setup_modifiers
import br_model


class PosConfig(br_model.BrModel):
    _inherit = 'pos.config'

    @api.model
    def _get_domain(self, user, domain):
        domain.append(('outlet_id.user_ids', 'in', [user.id]))
        return domain

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(PosConfig, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(result['arch'])
        if doc.xpath("//field[@name='stock_location_id']"):
            node = doc.xpath("//field[@name='stock_location_id']")[0]
            node.set('domain', "[('id', 'in', %s)]" % str(self.env.user.location_ids.ids))
            setup_modifiers(node, result['fields']['stock_location_id'])
        result['arch'] = etree.tostring(doc)
        return result
