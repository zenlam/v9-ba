# -*- coding: utf-8 -*-
from openerp import api, fields, models, _
from openerp.exceptions import Warning


class web_hide_duplicate(models.Model):
    _name = 'web.hide.duplicate'

    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               help="The model this field belongs to")
    hide_duplicate = fields.Boolean(string='Hide Duplicate')

    @api.constrains('model_id')
    def _check_for_duplicate(self):
        if len(self.search([('model_id', '=', self.model_id.id),('id','!=',self.id)])) > 1:
            raise Warning(_('Record with same model is already exists!'))
