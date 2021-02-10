# -*- coding: utf-8 -*-
from openerp import models, fields, api, SUPERUSER_ID, _
from openerp.exceptions import ValidationError


class br_country_state(models.Model):
    _inherit = 'res.country.state'

    parent_id = fields.Many2one(comodel_name='res.country.state', string=_("Parent Area"))


class br_multi_outlet_region_area(models.Model):
    _name = 'br_multi_outlet.region_area'
    _description = 'Region'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    parent_id = fields.Many2one(comodel_name="br_multi_outlet.region_area", string=_("Parent Region"))


class br_multi_outlet_outlet_type(models.Model):
    _name = 'br_multi_outlet.outlet_type'

    name = fields.Char(required=True, string='Name')
    is_active = fields.Boolean('Active', default="1")
    type = fields.Selection(
        [('asset_type', 'Asset Type'), ('location_type', 'Location Type')], 'Type', required=True)
    parent_id = fields.Many2one(comodel_name="br_multi_outlet.outlet_type", string=_("Parent Type"))


class BrOuteRoute(models.Model):
    _name = 'br.outlet.route'

    name = fields.Char(string="Name")
    description = fields.Text(string="Description")
    outlet_ids = fields.One2many(string="Outlet(s)", comodel_name='br_multi_outlet.outlet', inverse_name='route_id', ondelete='set null')
    active = fields.Boolean(string="Active", default=True)


class br_multi_outlet_outlet(models.Model):
    _name = 'br_multi_outlet.outlet'
    _description = "Br Multi Outlets"
    _inherit = ['mail.thread']

    # Outlet Information
    name = fields.Char("Outlet Name", required=True, copy=False, track_visibility='onchange')
    code = fields.Char("Code", required=True, copy=False, track_visibility='onchange')
    company_id = fields.Many2one(comodel_name='res.company', string='Company', required=True, index=1, default=lambda self: self.env.user.company_id)
    route_id = fields.Many2one(string="Route", comodel_name='br.outlet.route', ondelete='restrict')
    asset_type = fields.Many2one('br_multi_outlet.outlet_type', "Asset Type", required=True, track_visibility='onchange')
    location_type = fields.Many2one('br_multi_outlet.outlet_type', "Location Type", required=True, track_visibility='onchange')
    status = fields.Selection([
        ('open', 'Open New'),
        ('open_non_comps', 'Open Non Comps'),
        ('open_comps', 'Open Comps'),
        ('permanent_close', 'Permanent Close'),
        ('tempclosed', 'Temporary Close'),
        ('special', 'Under Renovation'),
    ], 'Status', required=True, default='open', track_visibility='onchange')
    outlet_type = fields.Selection([
        ('standard', 'Standard'),
        ('premium', 'Premium'),
    ], 'Outlet Type', required=True, default='standard', track_visibility='onchange')
    note = fields.Text('Remark')
    state_id = fields.Many2one(
        'res.country.state',
        'Area',
        ondelete='restrict', required=True, track_visibility='onchange')
    region_area_id = fields.Many2one(
        'br_multi_outlet.region_area',
        'Region',
        ondelete='restrict', track_visibility='always')

    # Outlet Contact
    outlet_phone = fields.Char('Phone')
    outlet_mobile = fields.Char('Mobile')
    outlet_fax = fields.Char('Fax')
    outlet_email = fields.Char('Email')
    outlet_name = fields.Char('Name')
    outlet_street1 = fields.Char('Street 1')
    outlet_street2 = fields.Char('Street 2')
    outlet_city = fields.Char('City')
    outlet_zip = fields.Char('Zip')
    outlet_country = fields.Many2one(
        'res.country', 'Country', ondelete='restrict')

    # Outlet contact Ship
    other_address = fields.Boolean('Shipping Other Address')
    outlet_name_ship = fields.Char('Name')
    outlet_state_ship = fields.Many2one('res.country.state')
    outlet_street1_ship = fields.Char('Street')
    outlet_street2_ship = fields.Char('Street')
    outlet_zip_ship = fields.Char('Zip')
    outlet_city_ship = fields.Char('City')
    outlet_country_ship = fields.Many2one(
        'res.country', 'Country', ondelete='restrict')

    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Price List',
        required=True, track_visibility='onchange')

    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string='Warehouse', required=True, track_visibility='onchange')

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')], track_visibility='always')

    fiscal_position_ids = fields.Many2many('account.fiscal.position', string='Fiscal Position', track_visibility='always')
    outlet_number = fields.Char(string='Outlet Number')
    user_ids = fields.Many2many(
        'res.users',
        string='Users',
        help='User for Outlet')

    outlet_tags = fields.Many2many(string=_("Tags"), comodel_name='br.outlet.tag')

    # them field vao tab User
    region_manager = fields.Many2one('res.users', string="Regional Manager")
    area_manager = fields.Many2one('res.users', string="Area Manager")
    oultet_pic1 = fields.Many2one('res.users', string="Outlet PIC 1")
    oultet_pic2 = fields.Many2one('res.users', string="Outlet PIC 2")
    oultet_pic3 = fields.Many2one('res.users', string="Outlet PIC 3")
    # them field vao tab Status
    open_hour = fields.Float(string="Open Hour")
    close_hour = fields.Float(string="Close Hour")
    open_date = fields.Date(string="Open Date")
    close_date = fields.Date(string="Close Date")
    history_ids = fields.One2many('br.history.outlet', 'outlet_id', string="History")

    _sql_constraints = [
        ('constraint_unique_code',
         'UNIQUE(code)',
         _('Duplicate code field! Code of Outlet is unique key, you should choose other for this Outlet')),
        ('constraint_unique_warehouse',
         'UNIQUE(warehouse_id)',
         _('Duplicate warehouse field! Warehouse of Outlet is unique key, you should choose other for this Outlet')),
    ]

    @api.constrains('open_date', 'close_date')
    def _check_open_close_date(self):
        for record in self:
            if record.open_date > record.close_date and record.close_date and record.open_date:
                raise ValidationError("Close date must greater than Open date")

    @api.constrains('open_hour', 'close_hour')
    def _check_open_close_hour(self):
        for record in self:
            if (record.open_hour > 24) or (record.open_hour < 0) or (record.close_hour > 24) or (record.close_hour < 0):
                raise ValidationError("Close hour and Open hour must greater than 0 and less than 24")

    @api.model
    def create(self, vals):
        if 'history_ids' not in vals:
            history_vals = {
                'outlet_id': self.id,
                'region_manager': vals['region_manager'] if 'region_manager' in vals else None,
                'area_manager': vals['area_manager'] if 'area_manager' in vals else None,
                'oultet_pic1': vals['oultet_pic1'] if 'oultet_pic1' in vals else None,
                'oultet_pic2': vals['oultet_pic2'] if 'oultet_pic2' in vals else None,
                'oultet_pic3': vals['oultet_pic3'] if 'oultet_pic3' in vals else None,
                'asset_type': vals['asset_type'] if 'asset_type' in vals else None,
                'location_type': vals['location_type'] if 'location_type' in vals else None,
                'status': vals['status'] if 'status' in vals else None,
                'state_id': vals['state_id'] if 'state_id' in vals else None,
                'region_area_id': vals['region_area_id'] if 'region_area_id' in vals else None,
                'outlet_type': vals['outlet_type'] if 'outlet_type' in vals else None
            }
            vals.update(history_ids=[(0, 0, history_vals)])
        return super(br_multi_outlet_outlet, self).create(vals)

    @api.multi
    def write(self, vals):
        res = super(br_multi_outlet_outlet, self).write(vals)
        f = [
            'region_manager',
            'area_manager',
            'oultet_pic1',
            'oultet_pic2',
            'oultet_pic3',
            'asset_type',
            'location_type',
            'status',
            'state_id',
            'region_area_id',
            'outlet_type'
        ]
        if any([x in vals for x in f]):
            history_vals = {
                'outlet_id': self.id,
                'region_manager': vals['region_manager'] if 'region_manager' in vals else self.region_manager.id,
                'area_manager': vals['area_manager'] if 'area_manager' in vals else self.area_manager.id,
                'oultet_pic1': vals['oultet_pic1'] if 'oultet_pic1' in vals else self.oultet_pic1.id,
                'oultet_pic2': vals['oultet_pic2'] if 'oultet_pic2' in vals else self.oultet_pic2.id,
                'oultet_pic3': vals['oultet_pic3'] if 'oultet_pic3' in vals else self.oultet_pic3.id,
                'asset_type': vals['asset_type'] if 'asset_type' in vals else self.asset_type.id,
                'location_type': vals['location_type'] if 'location_type' in vals else self.location_type.id,
                'status': vals['status'] if 'status' in vals else self.status,
                'state_id': vals['state_id'] if 'state_id' in vals else self.state_id.id,
                'region_area_id': vals['region_area_id'] if 'region_area_id' in vals else self.region_area_id.id,
                'outlet_type': vals['outlet_type'] if 'outlet_type' in vals else self.outlet_type
            }
            self.env['br.history.outlet'].create(history_vals)
        return res


class br_history_outlet(models.Model):
    _name = 'br.history.outlet'
    _order = 'create_date desc'

    outlet_id = fields.Many2one('br_multi_outlet.outlet', string='Outlet')
    region_manager = fields.Many2one('res.users', string="Regional Manager")
    area_manager = fields.Many2one('res.users', string="Area Manager")
    # FIXME: Typo in field name
    oultet_pic1 = fields.Many2one('res.users', string="Outlet PIC 1")
    oultet_pic2 = fields.Many2one('res.users', string="Outlet PIC 2")
    oultet_pic3 = fields.Many2one('res.users', string="Outlet PIC 3")

    asset_type = fields.Many2one('br_multi_outlet.outlet_type', "Asset Type", required=True, track_visibility='onchange')
    location_type = fields.Many2one('br_multi_outlet.outlet_type', "Location Type", required=True, track_visibility='onchange')
    status = fields.Selection([
        ('open', 'Open New'),
        ('open_non_comps', 'Open Non Comps'),
        ('open_comps', 'Open Comps'),
        ('permanent_close', 'Permanent Close'),
        ('tempclosed', 'Temporary Close'),
        ('special', 'Under Renovation'),
    ], 'Status', required=True, default='open', track_visibility='onchange')
    state_id = fields.Many2one(
        'res.country.state',
        'Area',
        ondelete='restrict', required=True, track_visibility='onchange')
    region_area_id = fields.Many2one(
        'br_multi_outlet.region_area',
        'Region',
        ondelete='restrict', track_visibility='always')
    outlet_type = fields.Selection([
        ('standard', 'Standard'),
        ('premium', 'Premium'),
    ], 'Outlet Type', required=True)
