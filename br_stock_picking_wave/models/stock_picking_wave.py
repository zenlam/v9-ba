from openerp import models, fields, api, SUPERUSER_ID, _
from openerp.exceptions import UserError

class br_stock_warehouse(models.Model):
    _inherit = 'stock.picking.wave'

    def done(self, cr, uid, ids, context=None):
        picking_todo = set()
        for wave in self.browse(cr, uid, ids, context=context):
            for picking in wave.picking_ids:
                if picking.state in ('cancel', 'done'):
                    continue
                if picking.state != 'assigned':
                    raise UserError(_(
                        'Some pickings are still waiting for goods. Please check or force their availability before setting this wave to done.'))
                message_body = "<b>%s:</b> %s <a href=#id=%s&view_type=form&model=stock.picking.wave>%s</a>" % (
                _("Transferred by"), _("Picking Wave"), wave.id, wave.name)
                picking.message_post(body=message_body)
                picking_todo.add(picking.id)

                # baskin: update qty_done in stock_pack_operation before done picking
                for operation in picking.pack_operation_product_ids:
                    self.pool.get('stock.pack.operation').write(cr, uid, operation.id, {'qty_done': operation.product_qty})
        if picking_todo:
            self.pool.get('stock.picking').action_done(cr, uid, list(picking_todo), context=context)
        return self.write(cr, uid, ids, {'state': 'done'}, context=context)


