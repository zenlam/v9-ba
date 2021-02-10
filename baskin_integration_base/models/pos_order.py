# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class POSOrder(models.Model):
    _inherit = "pos.order"

    member_code = fields.Char(string='Membership Code')
    member_id = fields.Many2one('third.party.member', string='Membership ID')
    member_name = fields.Char(related='member_id.name', string='Member Name')
    third_party = fields.Many2one('third.party', string='Third Party')
    sync_id = fields.Char(string='Sync ID', copy=False)

    @api.model
    def _order_fields(self, ui_order):
        """
        add the member_code and member_id to the dictionary
        """
        res = super(POSOrder, self)._order_fields(ui_order)
        # handle the scenario the POS is offline and scan member code but
        # unable to retrieve the member id. After syncing the order to backend,
        # try to search the member id based on member code in Odoo db
        # Danger: do not call the query_member here, the API might raise Error
        # and this will stop the POS order creation.
        if ui_order.get('member_code') and not ui_order.get('member_id'):
            member_id = self.env['third.party.member'].search([
                ('code', '=', ui_order.get('member_code'))])
            if member_id:
                ui_order['member_id'] = member_id.id
        res.update({
            'member_id': ui_order.get('member_id', False),
            'member_code': ui_order.get('member_code', False),
            'third_party': ui_order.get('third_party', False)
        })
        return res

    @api.model
    def _process_order(self, ui_order):
        """
        Sync the transaction data to the third party if the third party
        requires Odoo to sync order data
        """
        res = super(POSOrder, self)._process_order(ui_order)
        order = self.browse(res)
        if order.third_party and order.third_party.sync_order_data:
            order.sync_transaction()
        return res

    @api.multi
    def sync_transaction(self):
        """ Sync the POS Order transaction detail to the third party. Inherit
        this function to perform the transaction synchronization """
        return

    @api.multi
    def sync_cancel_transaction(self):
        """ Sync the cancelled POS Order transaction detail to the third party.
         Inherit this function to perform the transaction synchronization """
        return

    @api.model
    def get_pos_order_membership_id(self):
        """
        Cron job function to fill in missing membership id in pos order
        """
        return
