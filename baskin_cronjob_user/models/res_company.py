from openerp import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    cronjob_user = fields.Many2one('res.users',
                                   string='Cronjob User',
                                   required=True)
