from openerp import fields, models, api, _


class PosConfig(models.Model):
    _inherit = 'pos.config'

    freeze_interval = fields.Float(compute='_get_freeze_interval', digits=(18, 2))

    @api.multi
    def _get_freeze_interval(self):
        interval = float(self.env['ir.config_parameter'].sudo().get_param('pos_freeze_screen_interval', default=1))
        for config in self:
            config.freeze_interval = interval
