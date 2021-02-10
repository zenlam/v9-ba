# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from openerp.exceptions import ValidationError, UserError


class ThirdParty(models.Model):
    _name = "third.party"
    _description = "Third party platform to be integrated"

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Short Code', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=1,
        default=lambda self: self.env.user.company_id)
    is_baskin = fields.Boolean(string='Is Baskin Robbin', default=False)
    # API configuration
    has_api = fields.Boolean(string='Has API', default=False)
    api_url = fields.Char(string='API URL')
    # Data Syncing Checkboxes
    sync_promotion_data = fields.Boolean(string='Promotion Syncing',
                                         default=False)
    sync_outlet_data = fields.Boolean(string='Outlet Syncing',
                                      default=False)
    sync_menu_data = fields.Boolean(string='Menu Syncing',
                                    default=False)
    sync_member_data = fields.Boolean(string='Member Syncing',
                                      default=False)
    sync_order_data = fields.Boolean(string='POS Order Syncing',
                                     default=False)
    # Data Syncing Linkage
    promotion_ids = fields.One2many('br.bundle.promotion',
                                    'third_party_id',
                                    string='Promotions')
    outlet_sync_ids = fields.One2many('third.party.outlet.sync',
                                      'third_party_id',
                                      string='Outlet Syncing')
    menu_sync_ids = fields.One2many('third.party.menu.sync',
                                    'third_party_id',
                                    string='Menu Syncing')
    member_ids = fields.One2many('third.party.member',
                                 'third_party_id',
                                 string='Members')
    order_ids = fields.One2many('pos.order',
                                'third_party',
                                string='POS Orders')
    # Data API Endpoint
    promotion_sync_endpoint = fields.Char(string='Promotion Sync Endpoint')
    outlet_sync_endpoint = fields.Char(string='Outlet Sync Endpoint')
    menu_sync_endpoint = fields.Char(string='Menu Sync Endpoint')
    order_sync_endpoint = fields.Char(string='POS Order Sync Endpoint')
    order_cancel_sync_endpoint = fields.Char(string='POS Order Cancellation '
                                                    'Sync Endpoint')
    coupon_code_update_endpoint = fields.Char(
        string='Coupon Code Update Endpoint')
    # Individual API
    create_code_api = fields.Boolean(string='Allow Create Coupon',
                                     default=False)
    create_member_api = fields.Boolean(string='Allow Create Member',
                                       default=False)
    # Member Configuration
    member_code_prefix = fields.Char(string='Member Code Prefix')
    # Data Count
    promotion_count = fields.Integer(compute='_promotion_count',
                                     string='Promotion Count')
    outlet_count = fields.Integer(compute='_outlet_count',
                                  string='Outlet Count')
    menu_count = fields.Integer(compute='_menu_count',
                                string='Menu Count')
    member_count = fields.Integer(compute='_member_count',
                                  string='Member Count')
    order_count = fields.Integer(compute='_order_count',
                                 string='POS Order Count')

    def _promotion_count(self):
        """ compute the total promotions of this third party """
        for record in self:
            record.promotion_count = len(record.promotion_ids)

    def _outlet_count(self):
        """ compute the total outlets of this third party """
        for record in self:
            record.outlet_count = len(record.outlet_sync_ids)

    def _menu_count(self):
        """ compute the total menus of this third party """
        for record in self:
            record.menu_count = len(record.menu_sync_ids)

    def _member_count(self):
        """ compute the total members of this third party """
        for record in self:
            record.member_count = len(record.member_ids)

    def _order_count(self):
        """ compute the total orders of this third party """
        for record in self:
            record.order_count = len(record.order_ids)

    @api.constrains('is_baskin')
    def _check_is_baskin(self):
        count = len(self.search([
            ('is_baskin', '=', True),
            ('company_id', '=', self.env.user.company_id.id)]))
        if count > 1:
            raise ValidationError(_("There can be only one Baskin-Robbins "
                                    "platform per company."))

    @api.constrains('member_code_prefix')
    def _check_member_code_prefix(self):
        if self.member_code_prefix:
            count = len(self.search([
                ('member_code_prefix', '=', self.member_code_prefix)]))
            if count > 1:
                raise ValidationError(_(
                    "Member Code Prefix should be Unique!"))

    @api.multi
    def query_member(self, member_code):
        """ Query the member information based on the member code from third
        party. Inherit this function to perform querying logic from Third Party
        """
        return False

    @api.multi
    def query_coupon(self, coupon_code):
        """ Query the coupon's member information based on the coupon code
        from third party. Inherit this function to perform querying logic from
        Third Party
        """
        return False

    @api.multi
    def action_view_promotions(self):
        """ Function to show a tree view of related promotions view """
        action = self.env.ref('br_discount.br_bundle_promotion')
        result = action.read()[0]
        promotion_ids = self.promotion_ids.ids
        result['domain'] = "[('id','in',[" + ','.join(
            map(str, promotion_ids)) + "])]"
        return result

    @api.multi
    def action_view_outlets(self):
        """ Function to show a tree view of related outlet view """
        action = self.env.ref(
            'baskin_integration_base.third_party_outlet_sync_action')
        result = action.read()[0]
        result['context'] = {'default_third_party_id': self.id}
        outlet_sync_ids = self.outlet_sync_ids.ids
        result['domain'] = "[('id','in',[" + ','.join(
            map(str, outlet_sync_ids)) + "])]"
        return result

    @api.multi
    def action_view_menus(self):
        """ Function to show a tree view of related menus view """
        action = self.env.ref(
            'baskin_integration_base.third_party_menu_sync_action')
        result = action.read()[0]
        menu_sync_ids = self.menu_sync_ids.ids
        result['domain'] = "[('id','in',[" + ','.join(
            map(str, menu_sync_ids)) + "])]"
        return result

    @api.multi
    def action_view_members(self):
        """ Function to show a tree view of related members view """
        action = self.env.ref(
            'baskin_integration_base.third_party_member_action')
        result = action.read()[0]
        member_ids = self.member_ids.ids
        result['domain'] = "[('id','in',[" + ','.join(
            map(str, member_ids)) + "])]"
        return result

    @api.multi
    def action_view_orders(self):
        """ Function to show a tree view of related orders view """
        action = self.env.ref(
            'baskin_integration_base.third_party_order_action')
        result = action.read()[0]
        order_ids = self.order_ids.ids
        result['domain'] = "[('id','in',[" + ','.join(
            map(str, order_ids)) + "])]"
        return result

    @api.multi
    def add_all_outlet(self):
        """ Function to populate all outlets to this third party """
        for res in self:
            outlet_sync_ids = self.env['third.party.outlet.sync'].search([
                ('third_party_id', '=', res.id)])
            existing_outlet = [sync.outlet_id.id for sync in outlet_sync_ids]
            all_outlet_ids = self.env['br_multi_outlet.outlet'].search([
                ('company_id', '=', res.company_id.id),
                ('id', 'not in', existing_outlet)])

            # create third party outlet sync
            for outlet in all_outlet_ids:
                self.env['third.party.outlet.sync'].create({
                    'third_party_id': res.id,
                    'outlet_id': outlet.id
                })


class ThirdPartyMember(models.Model):
    _name = "third.party.member"
    _description = "Member in third party platform"

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Member Code', required=True)
    member_level = fields.Char(string='Member Level', required=True)
    third_party_id = fields.Many2one('third.party',
                                     string='Third Party Platform',
                                     required=True)
    company_id = fields.Many2one(related='third_party_id.company_id',
                                 string='Company')
    is_opt_out = fields.Boolean(string='Opt Out?', default=False,
                                readonly=True)

    @api.model
    def create(self, vals):
        """ raise error if the member already exists in system
        P.S. Using create function instead of api.constrains because
        api.constrains still create the record even though it raises
        ValidationError. This is due to the creation is from backend API call,
        but not from UI.
        """
        if len(self.search([('code', '=', vals.get('code'))])) >= 1:
            raise UserError(_('Member already exists.'))
        return super(ThirdPartyMember, self).create(vals)

    @api.model
    def get_member_data(self, member_code, third_party_id):
        """ return member information based on the member code provided """
        member = self.search([('code', '=', member_code),
                              ('third_party_id', '=', third_party_id)],
                             limit=1)
        if member:
            if member.is_opt_out:
                raise ValidationError(_('Member Opted Out!'))
            else:
                return {
                    'id': member.id,
                    'name': member.name,
                    'code': member.code
                }
        else:
            # call the third party query member function
            third_party = self.env['third.party'].browse(third_party_id)
            member = third_party.query_member(member_code)
            if member:
                return {
                    'id': member.id,
                    'name': member.name,
                    'code': member.code
                }

    @api.multi
    def opt_out(self):
        """ perform the member opt out action, inherit this function to
        perform the respective opt out action
        """
        return True


class ThirdPartyOutletSync(models.Model):
    _name = "third.party.outlet.sync"
    _description = "An intermediate table between Outlet and Third Party"

    name = fields.Char(compute='_get_name', string='Name', store=True)
    third_party_id = fields.Many2one('third.party', string='Third Party',
                                     required=True,
                                     domain=[('sync_outlet_data', '=', True)])
    outlet_id = fields.Many2one('br_multi_outlet.outlet', string='Outlet',
                                required=True)
    sync_id = fields.Char(
        string='Sync ID', readonly=1, copy=False,
        help='The record ID of third party database. The value is returned '
             'from the third party after Odoo syncing the data.')
    last_sync_info = fields.Char(string='Last Sync Information')

    @api.depends('third_party_id', 'outlet_id')
    def _get_name(self):
        for rec in self:
            rec.name = "/"
            if rec.third_party_id and rec.outlet_id:
                rec.name = rec.third_party_id.code + '-' + rec.outlet_id.code

    @api.multi
    def sync_data(self):
        """
        Sync the outlet data to third party. Inherit this function to perform
        data syncing between Odoo and Third Party
        """
        return


class ThirdPartyOutletSyncLog(models.Model):
    _name = 'third.party.outlet.sync.log'
    _description = 'Log file that keep track the outlet master data syncing.'
    _order = 'sync_datetime desc'

    sync_datetime = fields.Datetime(string='Sync Time')
    sync_info = fields.Html(string='Sync Information')
    sync_status = fields.Selection([('success', 'Success'), ('fail', 'Fail'),
                                    ('unreachable', 'Unreachable')],
                                   string='Sync Status', default='unreachable')
    rec_id = fields.Char(string='Outlet Code')
    rec_name = fields.Char(string='Outlet Name')
    third_party_id = fields.Many2one('third.party', string='Third Party')
    third_party_code = fields.Char(related='third_party_id.code',
                                   string='Third Party Name',
                                   store=True)


class ThirdPartyMenuSync(models.Model):
    _name = "third.party.menu.sync"
    _description = "An intermediate table between Menu and Third Party"

    name = fields.Char(compute='_get_name', string='Name', store=True)
    third_party_id = fields.Many2one('third.party', string='Third Party',
                                     required=True,
                                     domain=[('sync_menu_data', '=', True)])
    menu_id = fields.Many2one('product.product', string='Menu Name',
                              required=True)
    sync_id = fields.Char(
        string='Sync ID', readonly=1, copy=False,
        help='The record ID of third party database. The value is returned '
             'from the third party after Odoo syncing the data.')
    last_sync_info = fields.Char(string='Last Sync Information')

    @api.depends('third_party_id', 'menu_id')
    def _get_name(self):
        for rec in self:
            rec.name = "/"
            if rec.third_party_id and rec.menu_id:
                rec.name = rec.third_party_id.code + '-' + rec.menu_id.name

    @api.multi
    def sync_data(self):
        """
        Sync the menu data to third party. Inherit this function to perform
        data syncing between Odoo and Third Party
        """
        return
