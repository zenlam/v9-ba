from openerp import models, api, fields, _
from datetime import datetime
from openerp.exceptions import ValidationError


class StockTransferDispute(models.TransientModel):
    _name = 'stock.transfer.dispute'

    pick_id = fields.Many2one(comodel_name='stock.picking', string="Transfer")
    details_ids = fields.One2many(comodel_name='stock.transfer.dispute.details', inverse_name='dispute_id',
                                  string="Details")

    @api.multi
    def process_dispute(self):
        """
        Raise dispute if there is difference in real quantity and theoretical quantity.
        Let difference qty = real_qty - theoretical_qty, if difference < 0 then do reverse transfer
        else create new transfer to fulfill the lost qty
        :return:
        """
        return_picking_obj = self.env['stock.return.picking']
        return_picking_line_obj = self.env['stock.return.picking.line']
        picking_type_id = self.env.ref('br_stock_request.br_dispute_picking_type').id
        if self.env.user.company_id.id == 3:
            picking_type_id = self.env.ref('br_stock_request.br_dispute_picking_type_mega').id
        to_reverse = []
        to_create = []
        for line in self.details_ids:
            if line.diff_qty < 0:
                to_reverse.append({
                    'product_id': line.product_id.id,
                    'quantity': -line.diff_qty,
                    'move_id': line.move_id.id
                })
            elif line.diff_qty > 0:
                val = {
                    'request_line_id': line.move_id.request_line_id.id,
                    'name': '[%s] %s' % (line.product_id.code, line.product_id.name_template),
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.diff_qty,
                    'account_analytic_id': line.move_id.account_analytic_id.id,
                    'product_uom': line.move_id.product_uom.id,
                    'picking_type_id': picking_type_id,
                    'is_dispute_move': True,
                    'request_id': line.move_id.request_line_id.transfer_id.id,
                    'initial_move_qty': line.diff_qty
                }
                if not line.move_id:
                    val.update(product_uom=line.system_uom.id, account_analytic_id=self.pick_id.location_dest_id.get_analytic_account())
                to_create.append((0, 0, val))
            if line.move_id and line.diff_qty:
                line.move_id.request_line_id.dispute_qty += line.diff_qty
        request = self.pick_id.request_id
        if to_reverse or to_create:
            if request and not request.dispute_time:
                request.write({'dispute_time': datetime.now()})
            if to_reverse:
                return_picking = return_picking_obj.with_context(active_ids=[self.pick_id.id]).create({})
                return_picking.product_return_moves.unlink()
                for val in to_reverse:
                    val.update(wizard_id=return_picking.id)
                    return_picking_line_obj.create(val)
                new_ctx = self.env.context.copy()
                new_ctx['picking_type_id'] = picking_type_id
                new_ctx['skip_assign_picking'] = True
                return_picking.with_context(new_ctx).create_returns()
            if to_create:
                self.pick_id.copy({
                    'move_lines': to_create,
                    'picking_type_id': picking_type_id,
                    'picking_orig_id': self.pick_id.id
                })
        view = self.env.ref('br_stock_request.br_stock_request_transfer_form_view').id
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'br.stock.request.transfer',
            'res_id': request.id,
            'views': [(view, 'form')],
            'view_id': view,
        }

    @api.model
    def default_get(self, fields):
        result = super(StockTransferDispute, self).default_get(fields)
        picking_id = self.env.context.get('active_id')
        picking = self.env['stock.picking'].browse(picking_id)
        details_vals = []
        for move in picking.move_lines:
            val = {
                'move_id': move.id,
                'product_id': move.product_id.id,
                'system_uom': move.product_uom.id,
                'theo_qty': move.product_uom_qty,
                'real_qty': move.product_uom_qty,
                'diff_qty': 0,
                'is_from_transfer': True,
                'in_built': True
            }
            details_vals.append((0, 0, val))
        result.update(details_ids=details_vals, pick_id=picking_id)
        return result


class StockTransferDisputeDetails(models.TransientModel):
    _name = 'stock.transfer.dispute.details'

    dispute_id = fields.Many2one(comodel_name='stock.transfer.dispute', string="Dispute")
    product_id = fields.Many2one(string="Product", comodel_name='product.product')
    theo_qty = fields.Float(string="System Quantity", digits=(18, 2))
    real_qty = fields.Float(string="Actual Quantity", digits=(18, 2))
    diff_qty = fields.Float(string="Discrepancy", digits=(18, 2))
    diff_qty_related = fields.Float(related="diff_qty", string="Discrepancy", digits=(18, 2))
    move_id = fields.Many2one(string="Move", comodel_name='stock.move')
    is_from_transfer = fields.Boolean(string="Is Loaded From Transfer", default=False)
    system_uom = fields.Many2one(comodel_name="product.uom", string='UOM')
    in_built = fields.Boolean(default=False)

    @api.onchange('real_qty')
    @api.multi
    def _get_diff_qty(self):
        """Calculate difference between real and theoretical quantity"""
        for d in self:
            d.diff_qty = d.real_qty - d.theo_qty

    @api.onchange('product_id')
    def onchange_product_id(self):
        """Add domain to uom based on product_id selected"""
        res= {'domain': {}}
        if self.product_id:
            uom_ids = self.env['product.uom'].search([('product_tmpl_id', '=', self.product_id.product_tmpl_id.id)])
            res['domain']['system_uom'] = ['|', ('id', 'in', uom_ids.ids), ('id', '=', self.product_id.uom_id.id)]
        else:
            res['domain']['system_uom'] = []
        return res





