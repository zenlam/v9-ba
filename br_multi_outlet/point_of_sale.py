# -*- coding: utf-8 -*-
__author__ = 'truongnn'
from openerp import models, fields, api
from openerp import tools, models, SUPERUSER_ID
from lxml import etree
# TODO: check if filter outlet function is duplicated code
class pos_config(models.Model):
    _inherit = 'pos.config'

    outlet_id = fields.Many2one('br_multi_outlet.outlet', string='Outlet', ondelete='restrict')

    @api.onchange('outlet_id')
    def onchange_outlet(self):
        if self.outlet_id:
            self.stock_location_id = self.outlet_id.warehouse_id and self.outlet_id.warehouse_id.lot_stock_id.id
            self.pricelist_id = self.outlet_id.pricelist_id and self.outlet_id.pricelist_id.id
            self.fiscal_position_ids = self.outlet_id.fiscal_position_ids and [x.id for x in self.outlet_id.fiscal_position_ids]

    # def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
    #     if context and context.get('br_outlet', False):
    #         sql = '''
    #             select * from br_multi_outlet_outlet_res_users_rel where res_users_id=%s
    #         '''%(user)
    #         cr.execute(sql)
    #         item_ids = [x[0] for x in cr.fetchall()]
    #         args += [('outlet_id', 'in', item_ids)]
    #     return super(pos_config, self).search(cr, user, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def open_session_cb(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "you can open only one session at a time"

        proxy = self.pool.get('pos.session')
        record = self.browse(cr, uid, ids[0], context=context)
        current_session_id = record.current_session_id
        if not current_session_id:
            values = {
                'user_id': uid,
                'config_id': record.id,
                'outlet_id': record.outlet_id.id
            }
            session_id = proxy.create(cr, uid, values, context=context)
            self.write(cr, SUPERUSER_ID, record.id, {'current_session_id': session_id}, context=context)
            if record.current_session_id.state == 'opened':
                return self.open_ui(cr, uid, ids, context=context)
            return self._open_session(session_id)
        return self._open_session(current_session_id.id)

pos_config()

class pos_session(models.Model):
    _inherit = 'pos.session'

    outlet_id = fields.Many2one('br_multi_outlet.outlet', string='Outlet', ondelete='restrict')

    @api.onchange('outlet_id')
    def onchange_outlet(self):
        domain = {}
        if not self.outlet_id:
            return
        # domain['config_id'] = [('outlet_id', '=', self.outlet_id.id)]
        # return {'domain': domain}
        ls_config = self.env['pos.config'].search([('outlet_id', '=', self.outlet_id.id)], limit=1)
        self.config_id = ls_config
        return {'domain': {'config_id': [('outlet_id', 'in', [self.outlet_id.id])]}}


pos_session()

class pos_order(models.Model):
    _inherit = 'pos.order'

    outlet_id = fields.Many2one('br_multi_outlet.outlet', string='Outlet', ondelete='restrict')

pos_order()
