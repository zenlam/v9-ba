# -*- coding: utf-8 -*-
from openerp import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    attn_to = fields.Many2one('res.partner', string='Attn To')
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Point', readonly=True, required=True,
                                          states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                          help="Delivery address for current sales order.")
    area_id = fields.Many2one('customer.area', string='Area')
    state_id = fields.Many2one('res.country.state', string='State')

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        super(SaleOrder, self).onchange_partner_id()
        if self.partner_id:
            self.area_id = self.partner_id.area_id.id
            self.state_id = self.partner_id.state_id.id
            self.update({
                'partner_invoice_id': self.partner_id.id
            })

    @api.multi
    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals.update({
            'partner_shipping_id': self.partner_shipping_id.id,
            'attn_to': self.attn_to.id
        })
        return invoice_vals

