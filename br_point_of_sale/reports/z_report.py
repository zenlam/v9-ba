from openerp import fields, api, models, _
from datetime import datetime, timedelta
from openerp.exceptions import UserError

def cutoff_time(date):
    """
    Subtract 3 hours from datetime
    :param date: UTC datetime
    :return: date
    """
    date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S') - timedelta(hours=3)
    return date.strftime('%Y-%m-%d %H:%M:%S')

class ZReportForm(models.Model):
    _name = 'z.report'

    outlet_id = fields.Many2one(comodel_name='br_multi_outlet.outlet', string="Outlets")
    date = fields.Date(string="Date")

    @api.multi
    def action_print(self):
        from_date = cutoff_time(self.date + ' 00:00:00')
        to_date = cutoff_time(self.date + ' 23:59:59')
        dom = [('start_at', '>=', from_date), ('start_at', '<=', to_date), ('outlet_id', '=', self.outlet_id.id),
               ('state', '=', 'closed')]
        sessions = self.env['pos.session'].search(dom, order='start_at')
        if len(sessions) == 0:
            raise UserError(_("No session found"))
        return self.env['report'].get_action(self, 'z_report', data={'sessions': [x.id for x in sessions]})


class ZReport(models.AbstractModel):
    _name = 'report.z_report'

    @api.multi
    def render_html(self, data):
        z_report = self.env['z.report'].browse(data['context'].get('active_id', []))
        z_reports = self.env['z.report'].search([('date', '=', z_report.date), ('outlet_id', '=', z_report.outlet_id.id)])
        sessions = self.env['pos.session'].browse(data['sessions'])
        pos_configs = self.env['pos.config'].search([('outlet_id', '=', z_report.outlet_id.id), ('state', '=', 'active')])
        docargs = {
            'doc_ids': sessions.ids,
            'doc_model': 'pos.session',
            'docs': sessions,
            'no_of_printed': len(z_reports),
            'active_register': len(pos_configs)
        }
        return self.env['report'].render('br_point_of_sale.x_report', docargs)
