# -*- coding: utf-8 -*-
from openerp import api, fields, models, _
from openerp.exceptions import Warning


class IrModelFieldsOptions(models.Model):
    _name = 'ir.model.fields.options'

    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               help="The model this field belongs to")
    field_id = fields.Many2one('ir.model.fields', string='Field',
                               required=True)
    no_open = fields.Boolean(string='no_open')
    no_create = fields.Boolean(string='no_create')
    no_create_edit = fields.Boolean(string='no_create_edit')

    @api.constrains('model_id', 'field_id')
    def _check_for_duplicate(self):
        if len(self.search([('model_id', '=', self.model_id.id),
                            ('field_id', '=', self.field_id.id)])) > 1:
            raise Warning(_('Record with same model & field is '
                            'already exists!'))

    @api.onchange('model_id', 'field_id')
    def onchange_model_id(self):
        if self.field_id and not self.model_id:
            warning = {
                'title': 'Warning',
                'message': _("Please, select Model first in-order "
                             "to select it's field!")}
            self.field_id = False
            return {'warning': warning}
        if self.model_id:
            return {'domain': {'field_id': [
                ('model_id', '=', self.model_id.id),
                ('ttype', 'in', ('many2one', 'many2many'))
                ]}}
