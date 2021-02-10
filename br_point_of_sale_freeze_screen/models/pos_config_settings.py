from openerp import fields, models, SUPERUSER_ID, api, _
from openerp.exceptions import ValidationError


class PosConfigSettings(models.TransientModel):
    _inherit = 'pos.config.settings'

    freeze_interval = fields.Float('Time to freeze POS screen', help='POS screen will be freeze after configured minute(s)', digits=(18,2))

    def get_default_file(self, cr, uid, fields, context=None):
        freeze_interval = self.pool.get('ir.config_parameter').get_param(cr, SUPERUSER_ID, 'pos_freeze_screen_interval', default=30, context=context)
        return {'freeze_interval': float(freeze_interval)}

    def set_default_file(self, cr, uid, ids, context=None):
        config = self.browse(cr, uid, ids[0], context)
        return self.pool.get('ir.config_parameter').set_param(cr, SUPERUSER_ID, 'pos_freeze_screen_interval', str(config.freeze_interval), context=context)

    @api.constrains('freeze_interval')
    def _check_freeze_interval(self):
        if self.freeze_interval <= 0:
            raise ValidationError(_("Time to freeze POS screen must be greater than zero !"))