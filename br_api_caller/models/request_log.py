from openerp import fields, models, api, _


class RequestLog(models.Model):
    _name = 'br.request.log'
    _order = 'name DESC'
    config_id = fields.Many2one(comodel_name='br.request.config', string=_("Config"))
    name = fields.Datetime(string=_("Date"))
    log_detail_ids = fields.One2many(comodel_name='br.request.log.details', inverse_name='log_id')

    def log(self, info):
        """
        Save log details
        @param info: dict - log information
        @return:
        """
        self.ensure_one()
        self.write({'log_detail_ids': info})

class RequestLogDetails(models.Model):
    _name = 'br.request.log.details'

    details = fields.Text(string=_("Response"))
    data = fields.Text(string=_("Sent Data"))
    status = fields.Selection(selection=[('failed', 'Failed'), ('success', 'Success')], string=_("Status"))
    request_id = fields.Many2one(comodel_name='br.request.details', string=_('Requests'))
    log_id = fields.Many2one(comodel_name='br.request.log')
