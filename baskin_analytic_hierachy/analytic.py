from openerp import models, fields, api

class AnalyticHierarchy(models.Model):
    _inherit = 'account.analytic.account'

    internal_type = fields.Selection([('view', 'View'), ('other', 'Regular')
                             ], 'Analytic Account Type', required=True, default='other')