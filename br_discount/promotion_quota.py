# --*-- coding: utf-8 --*--

from openerp import fields, api, models, SUPERUSER_ID
from datetime import datetime, timedelta
from openerp.exceptions import ValidationError


class br_bundle_promotion(models.Model):
    _inherit = 'br.bundle.promotion'
    _description = 'Promotion'

    quota_type = fields.Selection(string="Quota Share Policy", selection=[('individual', 'Individual'),('global', 'Global')], default=None,
                                  help="""
                                  * Individual: Validate promotion base on each outlet line's quota
                                  * Global: Validate promotion base on total quota of all outlet lines
                                  """, track_visibility='onchange')

    quota = fields.Float(string="Quota", track_visibility='always')
    used_quota = fields.Float(string="Used Quota", track_visibility='always')
    outlet_quota_lines = fields.One2many(comodel_name='br.promotion.outlet.quota', inverse_name='promotion_id',
                                         string="Outlet's quota")

    # Tab user
    user_quota_type = fields.Selection(string="Quota Type",
                                  selection=[
                                      ('quantity', 'Quantity'),
                                      ('amount', 'Amount'),
                                  ], track_visibility='onchange')
    user_quota = fields.Float(string="Quota", track_visibility='always')
    user_quota_reset = fields.Selection(string="Quota Reset",
                                       selection=[
                                           ('daily', 'Daily'),
                                           ('weekly', 'Weekly'),
                                           ('monthly', 'Monthly'),
                                           ('yearly', 'Yearly'),
                                       ], track_visibility='onchange')
    user_quota_lines = fields.One2many(comodel_name='br.promotion.user.quota', inverse_name='promotion_id',
                                         string="User's quota")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env['res.company']._company_default_get('account.account'), track_visibility='always')

    @api.multi
    def prepare_quota_outlet_lines(self):
        """
        @param used_quota: quota number
        @return outlet_quota_lines: lines which is created from existing outlets
        """
        if self.env.user.id != SUPERUSER_ID:
            outlets = self.env['br_multi_outlet.outlet'].search([('company_id', '=', self.env.user.company_id.id)])
        else:
            outlets = self.env['br_multi_outlet.outlet'].search([])
        outlet_quota_lines = []
        for outlet in outlets:
            outlet_quota_lines.append(
                (0, 0, {'outlet_id': outlet.id, 'used_quota': 0})
            )
        return outlet_quota_lines

    @api.one
    @api.constrains('user_quota_type', 'user_quota_lines')
    def _check_user_quota_type(self):
        if self.user_quota_type and len(self.user_quota_lines) == 0:
            raise ValidationError("Quota lines for users aren't set !")

    @api.one
    @api.constrains('quota_type', 'outlet_quota_lines')
    def _check_quota_type(self):
        if self.quota_type == 'individual' and len(self.outlet_quota_lines) == 0:
            raise ValidationError("Quota lines for outlets aren't set !")

    @api.onchange('quota_type', 'is_all_outlet')
    def onchange_quota_type(self):
        lines = []
        if self.is_all_outlet:
            lines = self.prepare_quota_outlet_lines()
        else:
            self.outlet_ids = []
            lines = []
        self.outlet_quota_lines = lines

    # bg Tao schedule reset user quota
    def create_schedule_reset(self, promotion, type_reset):
        osv_cron = self.env['ir.cron']
        if promotion:
            name = 'Reset User Quota ' + str(promotion.id) + '-' + promotion.name
            cron = osv_cron.search([('name', '=', name)], limit=1)
            vals = {
                'function': 'action_reset_user_quota',
                'args': '(' + str(promotion.id) + ',)',
                'name': name,
                'interval_type': self.get_interval_type(type_reset),
                'numbercall': '-1',
                'interval_number': 12 if type_reset == 'yearly' else 1,
                'nextcall': self.get_default_next_time_call(type_reset),
                'active': True,
                'model': 'br.bundle.promotion'
            }

            if len(cron) > 0:
                cron.update(vals)
            else:
                osv_cron.create(vals)

    def create_schedule_outlet_reset(self, promotion, type_reset):
        osv_cron = self.env['ir.cron']
        if promotion:
            name = 'Reset Outlet Quota ' + str(promotion.id) + '-' + promotion.name
            cron = osv_cron.search([('name', '=', name)], limit=1)
            vals = {
                'function': 'action_reset_outlet_quota',
                'args': '(' + str(promotion.id) + ',)',
                'name': name,
                'interval_type': self.get_interval_type(type_reset),
                'numbercall': '-1',
                'interval_number': 12 if type_reset == 'yearly' else 1,
                'nextcall': self.get_default_next_time_call(type_reset),
                'active': True,
                'model': 'br.bundle.promotion'
            }

            if len(cron) > 0:
                cron.update(vals)
            else:
                osv_cron.create(vals)

    def get_default_next_time_call(self, type_reset):
        today = datetime.today()
        if type_reset == 'daily':
            return datetime(today.year, today.month, today.day+1, 0, 0, 0)+ timedelta(hours=-7)
        if type_reset == 'weekly':
            cur_day_of_week = today.weekday()
            return datetime(today.year, today.month, today.day + (7 - cur_day_of_week), 0, 0, 0) + timedelta(hours=-7)
        if type_reset == 'monthly':
            return datetime(today.year, today.month+1, 1, 0, 0, 0)+ timedelta(hours=-7)
        if type_reset == 'yearly':
            return datetime(today.year+1, 1, 1, 0, 0, 0)+ timedelta(hours=-7)

    def get_interval_type(self, type_reset):
        if type_reset == 'daily':
            return 'days'
        if type_reset == 'weekly':
            return 'weeks'
        if type_reset == 'monthly' or type_reset == 'yearly':
            return 'months'

    @api.model
    def action_reset_quota(self, interval_type):
        # Reset outlet quota
        outlet_promotions = self.search([('outlet_quota_reset', '=', interval_type)])
        if outlet_promotions:
            outlet_quota_lines = self.env['br.promotion.outlet.quota']
            for promotion in outlet_promotions:
                for quota_line in promotion.outlet_quota_lines:
                    outlet_quota_lines = (outlet_quota_lines | quota_line)
            outlet_quota_lines.write({'used_quota': 0})

        # Reset user quota
        user_promotions = self.search([('user_quota_reset', '=', interval_type)])
        if user_promotions:
            user_quota_lines = self.env['br.promotion.user.quota']
            for promotion in user_promotions:
                for quota_line in promotion.user_quota_lines:
                    user_quota_lines = (user_quota_lines | quota_line)
            user_quota_lines.write({'used_quota': 0})

    @api.model
    def create(self, vals):
        if 'is_voucher' in vals and vals['is_voucher'] and 'user_quota_lines' in vals and vals['user_quota_lines']:
                raise ValidationError("Cannot apply both Voucher and User Quota for one promotion")
        res = super(br_bundle_promotion, self).create(vals)
        # if 'user_quota_reset' in vals and vals['user_quota_reset']:
        #     reset_type = vals['user_quota_reset']
        #     self.create_schedule_reset(res, reset_type)
        # if 'outlet_quota_reset' in vals and vals['outlet_quota_reset']:
        #     reset_type = vals['outlet_quota_reset']
        #     self.create_schedule_outlet_reset(res, reset_type)
        return res

    @api.multi
    def write(self, vals):
        is_voucher = vals['is_voucher'] if 'is_voucher' in vals else self.is_voucher
        is_group_user = False
        if 'user_quota_lines' in vals and vals['user_quota_lines']:
            if vals['user_quota_lines'][0] and vals['user_quota_lines'][0][2] and len(vals['user_quota_lines'][0][2]) > 0:
                is_group_user = True
        else:
            if self.user_quota_lines:
                is_group_user = True
        if is_voucher and is_group_user:
            raise ValidationError("Cannot apply both Voucher and User for one promotion")

        # user_quota_type = vals['user_quota_type'] if 'user_quota_type' in vals else self.user_quota_type
        # if user_quota_type and is_voucher:
        #     raise ValidationError(
        #         "Cannot apply voucher with user quota in one discount. Please select 1 option only")
        if 'is_all_outlet' in vals and vals['is_all_outlet']:
            existed_outlets = [x.outlet_id.id for x in self.outlet_quota_lines]
            new_quota_outlet_lines = []
            all_outlets = self.prepare_quota_outlet_lines()
            # If there is no outlet_quota_lines, insert all existing outlets to promotion
            # else check if outlet isn't in outlet_quota_lines then insert it
            if not existed_outlets:
                new_quota_outlet_lines = all_outlets
            else:
                for line in all_outlets:
                    if line[2]['outlet_id'] not in existed_outlets:
                        new_quota_outlet_lines.append(line)
            vals.update(outlet_quota_lines=new_quota_outlet_lines)
        # if 'user_quota_reset' in vals and vals['user_quota_reset']:
        #     reset_type = vals['user_quota_reset']
        #     self.create_schedule_reset(self[0], reset_type)
        # if 'outlet_quota_reset' in vals and vals['outlet_quota_reset']:
        #     reset_type = vals['outlet_quota_reset']
        #     self.create_schedule_outlet_reset(self[0], reset_type)
        return super(br_bundle_promotion, self).write(vals)

    @api.model
    def check_available_quota(self, outlet_id, promotion_id):
        promotion_obj = self.browse(promotion_id)
        quota_type = promotion_obj.quota_type

        # If not config quota or quota = 0 (means it's unlimited) then allow to choose promotion
        if not quota_type or promotion_obj.quota == 0:
            return [True, 999999]
        used_quota = 0
        if quota_type == 'individual':
            outlet_quota_line = promotion_obj.outlet_quota_lines.search(
                [('outlet_id', '=', outlet_id), ('promotion_id', '=', promotion_id)])
            used_quota = outlet_quota_line.used_quota
        elif quota_type == 'global':
            used_quota = promotion_obj.used_quota
        if used_quota < 0:
            return [True, 999999]
        return [used_quota < promotion_obj.quota, promotion_obj.quota - used_quota]

    @api.model
    def get_rate_outlet_user_quota(self, outlet_id, user_promotion, promotion_id):
        """
        :param outlet_id:
        :param user_promotion:
        :param promotion_id:
        :return: [is_applicable, available_quota, is_unlimited, used_quota]
        """
        promotion_obj = self.browse(promotion_id)
        quota_type = promotion_obj.quota_type
        user_quota_type = promotion_obj.user_quota_type
        promotion_quota = 0

        # If not config quota or quota = 0 (means it's unlimited) then allow to choose promotion
        if (not quota_type or promotion_obj.quota == 0) and (len(promotion_obj.user_quota_lines) == 0 or promotion_obj.user_quota == 0):
            return [True, 0, True, 0]
        used_quota = 0
        if quota_type == 'individual':
            # Why not use filter ? Search function will issue unnecessary query
            # outlet_quota_line = promotion_obj.outlet_quota_lines.search(
            #     [('outlet_id', '=', outlet_id), ('promotion_id', '=', promotion_id)], limit=1)
            outlet_quota_line = promotion_obj.outlet_quota_lines.filtered(lambda x: x.outlet_id.id == outlet_id)
            used_quota = outlet_quota_line.used_quota
            promotion_quota = promotion_obj.quota

        elif quota_type == 'global':
            used_quota = promotion_obj.used_quota
            promotion_quota = promotion_obj.quota
        elif user_quota_type == 'quantity' or user_quota_type == 'amount':
            user_promotion_id = user_promotion and int(user_promotion) or False
            user_quota_line = promotion_obj.user_quota_lines.filtered(lambda t: t.user_id.id == user_promotion_id)
            if len(user_quota_line) > 0:
                used_quota = user_quota_line[0].used_quota
                promotion_quota = promotion_obj.user_quota
        if used_quota < 0:
            return [True, 0, True, 0, used_quota]
        return [used_quota < promotion_quota, promotion_quota - used_quota, False, used_quota]

    @api.multi
    @api.onchange('user_group_ids')
    def onchange_user_group(self):
        if self.user_group_ids:
            user_groups = [x.id for x in self.user_group_ids]
            ls_users = self.env['res.users'].search([('discount_group_ids', 'in', user_groups)])
            ls_user_ids = [(0, 0, {'user_id': x.id, 'used_quota': 0}) for x in ls_users]
            if len(ls_user_ids) > 0:
                self.user_quota_lines = ls_user_ids
        else:
            self.user_quota_lines = []



class br_promotion_outlet_quota(models.Model):
    _name = 'br.promotion.outlet.quota'

    promotion_id = fields.Many2one(comodel_name='br.bundle.promotion', string="Promotion", ondelete='restrict')
    used_quota = fields.Float(string="Used Quota", digits=(10, 2))
    outlet_id = fields.Many2one(comodel_name='br_multi_outlet.outlet', string="Outlet")

    @api.constrains('outlet_id')
    def _check_outlet_id_required(self):
        for res in self:
            if not res.outlet_id:
                raise ValidationError('Outlet should not be empty!')


class br_multi_outlet(models.Model):
    _inherit = 'br_multi_outlet.outlet'

    @api.model
    def create(self, vals):
        """
        @param vals: outlet's value
        @return outlet: outlet object
         Generate outlet_quota_lines for promotions
        """
        outlet = super(br_multi_outlet, self).create(vals)
        promotions = self.env['br.bundle.promotion'].search([('is_all_outlet', '=', True), ('company_id', '=', outlet.company_id.id)])
        for promotion in promotions:
            outlet_quota_lines = [
                (0, 0, {'promotion_id': promotion.id, 'outlet_id': outlet.id, 'used_quota': 0})
            ]
            promotion.write({'outlet_quota_lines': outlet_quota_lines})
        return outlet


class br_promotion_user_quota(models.Model):
    _name = 'br.promotion.user.quota'
    _order = 'user_id'

    promotion_id = fields.Many2one(comodel_name='br.bundle.promotion', string="Promotion", ondelete='restrict')
    used_quota = fields.Float(string="Used Quota", digits=(10, 2))
    user_id = fields.Many2one(comodel_name='res.users', string="User")

    @api.constrains('user_id')
    def _check_user_id_required(self):
        for res in self:
            if not res.user_id:
                raise ValidationError('User should not be empty!')
