from openerp import models, fields, api, _
from lxml import etree
from openerp.exceptions import UserError, ValidationError

class wizard_account_tax(models.TransientModel):
	
	_name = "wizard.account.tax.chart"

	start_date = fields.Date("Start Date", required=True)
	end_date = fields.Date("End Date", required=True)
	target_move = fields.Selection([('posted', 'All Posted Entries'),
                                         ('all', 'All Entries'),
                                        ], 'Target Moves', required=True)


	@api.multi
	def account_tax_chart_open_window(self):

		if self.start_date > self.end_date:
			raise ValidationError(_('Error! end date should be greater than start date.'))

		mod_obj = self.env['ir.model.data']
		act_obj = self.env['ir.actions.act_window']
		context = self._context.copy()

		if context is None:
			context = {}

		result = mod_obj.get_object_reference('cot_hierarchy', 'view_tax_code_tree')
		id = result and result[1] or False
		result = act_obj.browse([id]).read()
		context.update({'start_date': self.start_date, 'end_date': self.end_date, 'state': self.target_move,'clear_breadcrumbs':True})
		view_id = self.env.ref('cot_hierarchy.view_tax_code_tree').id

		return {
            'name': _('Account Tax Charts'),
            'type': 'ir.actions.act_window',
            'view_type': 'tree,form',
            'view_mode': 'tree',
            'res_model': 'account.tax.code',
            'view_id': view_id,
            'domain': [('parent_id','=',False)],
            'context': context,
        }
