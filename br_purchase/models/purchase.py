# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError


class BRPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    @api.multi
    def button_approve(self):
        if self.state != 'purchase':
            return super(BRPurchaseOrder, self).button_approve()
        else:
            raise ValidationError(_('You are trying to approve Purchase Order'
                                    ' - %s which has already been approved !')
                                  % self.name)

    @api.multi
    def _inverse_date_planned(self):
        for order in self:
            if order.apply_date_planned:
                order.order_line.write({'date_planned': self.date_planned})

    @api.model
    def _default_picking_type(self):
        """
        Override Default Picking Type
        """

        # Sometime user forgot to key in picking type leading to wrong data since picking type is set by default
        # => no need to default picking type anymore
        return None

    group_id = fields.Many2one('procurement.group', string="Procurement Group", copy=False)
    date_planned = fields.Datetime(string='Scheduled Date', compute=False, inverse='_inverse_date_planned' ,required=True, index=True, oldname='minimum_planned_date')
    apply_date_planned = fields.Boolean(string="Apply Date For All Products", inverse='_inverse_date_planned')

    picking_type_id = fields.Many2one('stock.picking.type', 'Deliver To', states=READONLY_STATES, required=True, default=_default_picking_type, \
                                      help="This will determine picking type of incoming shipment")

class PurchaseOrderline(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('product_id')
    def onchange_product_id(self):
        res = super(PurchaseOrderline, self).onchange_product_id()
        if self.order_id.date_planned:
            self.date_planned = self.order_id.date_planned
        return res

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        res = super(PurchaseOrderline, self)._onchange_quantity()
        if self.order_id.date_planned:
            self.date_planned = self.order_id.date_planned
        return res