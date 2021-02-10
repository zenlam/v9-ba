from openerp import models, fields, api, _
from lxml import etree
from openerp.exceptions import UserError, ValidationError


class analytic_chart_wizard(models.TransientModel):
    _name = "analytic.chart.wizard"

    start_date = fields.Date("Start Date", required=True)
    end_date = fields.Date("End Date", required=True)
    target_move = fields.Selection([('posted', 'All Posted Entries'),
                                    ('all', 'All Entries'),
                                    ], 'Target Moves', required=True)

    @api.multi
    def analytic_chart_open_window(self):

        if self.start_date > self.end_date:
            raise ValidationError(_('Error! end date should be greater than start date.'))
        context = self._context.copy()

        if context is None:
            context = {}
        context.update({'date_from': self.start_date, 'date_to': self.end_date, 'state': self.target_move, 'clear_breadcrumbs': True, 'strict_range': True, 'view_all_analytic': True})
        view_id = self.env.ref('analytic_hierarchy.analytic_hierarchy_tree_view').id

        return {
            'name': _('Chart of Analytic'),
            'type': 'ir.actions.act_window',
            'view_type': 'tree,form',
            'view_mode': 'tree',
            'res_model': 'account.analytic.account',
            'view_id': view_id,
            'domain': [('parent_id', '=', False)],
            'context': context,
        }
