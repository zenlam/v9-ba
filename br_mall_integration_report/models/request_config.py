from openerp import api, models, fields, _, tools
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT




class RequestConfig(models.Model):
    _inherit = 'br.request.config'

    outlet_ids = fields.Many2one(comodel_name='br_multi_outlet.outlet', string=_("Outlet"), required=True)
    period = fields.Selection(selection=[('daily', 'Daily'), ('monthly', 'Monthly')], required=True, default='daily')

    @api.multi
    def send_requests_manual(self, *args, **kwargs):
        self.ensure_one()
        view = self.env.ref('br_mall_integration_report.br_run_request_config_form_view').id
        return {
            'name': _('Run Config'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'br.run.request.config',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'context': {'active_id': self.id},
        }


class RequestDetails(models.Model):
    _inherit = 'br.request.details'

    @api.model
    def mall_integration_request_body(self, date=False):
        if date:
            start_date = None
            # 5:01 is cutoff time
            end_date = datetime.strptime(date + ' 05:01:00', DEFAULT_SERVER_DATETIME_FORMAT)
            date = end_date
        else:
            start_date, end_date = self.get_date_range()

        report = self.env['gto.summary.report'].create({'date': end_date,
                                                        'from_date': start_date,
                                                        'outlet_ids': self.config_id.outlet_ids.id})
        data, cash = report.get_onsite_offsite_data(), report.get_cash_data()[0]['cash'] or 0
        return self.get_payload(data, date)

    def get_date_range(self):
        now = datetime.now() + timedelta(hours=8)
        if self.config_id.period == 'monthly':
            end_date = now.replace(day=1) - timedelta(days=1)
            start_date = now.replace(month=now.month - 1, day=1) - timedelta(days=1)
        elif self.config_id.period == 'daily':
            end_date = now - timedelta(days=1)
            start_date = None
        else:
            raise UserWarning(_("Config's period is missing !"))
        return start_date, end_date

    def get_payload(self, data, date):
        if date:
            # do not need to minus 1 day if the date is provided, because it is a manual sending
            day_before = date
        else:
            now = datetime.now() + timedelta(hours=8)
            day_before = now - timedelta(days=1)
        #sub_total = data['total'] - data['tax'] + data['discount_before_tax']
        return [{
            "ReceiptNo": day_before.strftime('%Y%m%d'),
            "ReceiptDateAndTime2": day_before.strftime('%Y-%m-%d 00:00:00'),
            "SubTotal": data['on_site_without_tax'], #sub_total,
            "DiscountPercent": 0.0, #round(float(data['discount']) / sub_total, 2) * 100 if sub_total else 0.0,
            "DiscountAmount": 0.0, #data['discount_before_tax'],
            "GstPercent": 6.0,
            "GstAmount": data['on_site_tax'],
            "ServiceChargePercent": 0.0,
            "ServiceChargeAmount": 0.0,
            "GrandTotal": data['on_site_with_tax'],
            "IsTest": True,
            "IsVoid": False
        }]
