from openerp import api, models, fields, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        if 'email' not in vals or not vals['email']:
            vals['email'] = vals['login']
        return super(ResUsers, self).create(vals)