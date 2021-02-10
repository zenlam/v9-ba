# -*- coding: utf-8 -*-

from openerp import models, fields, api
import openerp
from openerp import SUPERUSER_ID
from openerp.exceptions import ValidationError
from openerp.http import request
from collections import OrderedDict


def check_login(cr, login, password, context=None):
    res_user_obj = request.registry.get('res.users')
    res = res_user_obj.search(
        cr, SUPERUSER_ID, [
            ('id', '=', login)], context=context)
    if res and len(res) > 0:
        user_id = res[0]
        # check credentials
        try:
            res_user_obj.check_credentials(cr, user_id, password)
            return user_id
        except openerp.exceptions.AccessDenied:
            return False


class br_res_users(models.Model):
    _inherit = 'res.users'

    discount_group_ids = fields.Many2many(
        comodel_name='br.discount.group',
        string='Discount Groups'
    )

    @api.model
    def pos_check_login(self, login, password):
        uid_user = check_login(
            self.env.cr, login, password, self.env.context)
        if uid_user is None or not uid_user:
            raise ValidationError('Invalid username or password')
        else:
            return uid_user

    @api.multi
    def write(self, vals):        
        for user in self:
            if 'discount_group_ids' in vals and vals['discount_group_ids'] and vals['discount_group_ids'][0]:
                discount_group_obj = self.env['br.discount.group']
                if vals['discount_group_ids'][0][0] == 6:
                    for group_id in vals['discount_group_ids'][0][2]:
                        discount_group = discount_group_obj.browse(group_id)
                        discount_group.update_user_quota_promotion({'user_ids': [(None, None, [user.id])]})
                    to_remove_group_ids = [g.id for g in self.discount_group_ids if g not in vals['discount_group_ids'][0][2]]
                    if to_remove_group_ids:
                        to_remove_groups = discount_group_obj.browse(to_remove_group_ids)
                        to_remove_groups.remove_user_quota_promotion(user,new_group_ids=vals['discount_group_ids'][0][2])
        return super(br_res_users, self).write(vals)

    @api.model
    def create(self, values):
        res = super(br_res_users, self).create(values)
        discount_groups = values.get('discount_group_ids', [])
        if discount_groups and discount_groups[0][0] == 6:
            discount_groups = self.env['br.discount.group'].browse(discount_groups[0][2])
            for group_id in discount_groups:
                group_id.update_user_quota_promotion({'user_ids': [(None, None, [res.id])]})
        return res

    @api.multi
    def unlink(self):
        """
        When remove user, also remove promotion quota
        :return:
        """
        for user in self:
            promotion_quota = self.env['br.promotion.user.quota'].search(
                [('user_id', '=', user.id)])
            if promotion_quota:
                promotion_quota.unlink()
        return super(br_res_users, self).unlink()


class br_discount_group(models.Model):
    _name = 'br.discount.group'

    name = fields.Char(string='Name')
    user_ids = fields.Many2many(
        comodel_name='res.users',
        string='Discount Users',
    )

    @api.multi
    def write(self, vals):
        for group in self:
            if vals['user_ids'] and vals['user_ids'][0]:
                if vals['user_ids'][0][0] == 6:
                    group.update_user_quota_promotion(vals)
                    to_remove_users = group.user_ids.filtered(lambda x: x.id not in vals['user_ids'][0][2])
                    if to_remove_users:
                        group.remove_user_quota_promotion(to_remove_users)
        return super(br_discount_group, self).write(vals)

    def update_user_quota_promotion(self, vals):
        """Create new user for quota if that user haven't in the list"""
        users_quota = self.env['br.promotion.user.quota']
        for group in self:
            promotions = self.env['br.bundle.promotion'].search([('user_group_ids', '=', group.id)])
            for p in promotions:
                users_promotion = [x.user_id.id for x in p.user_quota_lines]
                for u_id in vals['user_ids'][0][2]:
                    if u_id not in users_promotion:
                        users_quota.create({'user_id': u_id, 'promotion_id': p.id})

    @api.multi
    def remove_user_quota_promotion(self, users, new_group_ids=False):
        """When remove user from discount group, the user should be removed from discount also"""
        for group in self:
            promotions = self.env['br.bundle.promotion'].search([('user_group_ids', '=', group.id)])
            if promotions:
                promo_users = {}
                for promotion in promotions:
                    promo_groups = promotion.user_group_ids.ids
                    for user in users:
                        user_discount_groups = new_group_ids if new_group_ids is not False else user.discount_group_ids.ids
                        all_groups = user_discount_groups + promo_groups
                        if len(all_groups) == len(set(all_groups)):
                            promo_users.setdefault(promotion.id, [])
                            promo_users[promotion.id].append(user.id)
                for p in promo_users:
                    users_quota = self.env['br.promotion.user.quota'].search([('promotion_id', '=', p), ('user_id', 'in', promo_users[p])])
                    if users_quota:
                        users_quota.unlink()
