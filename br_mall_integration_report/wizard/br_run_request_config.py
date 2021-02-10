from openerp import models, api, fields, _
from openerp.addons.br_api_caller.models.api_caller import ApiCaller


class BrRunRequestConfig(models.TransientModel):
    _name = "br.run.request.config"

    date = fields.Date(string="Date", required=True)
    config_id = fields.Many2one(comodel_name='br.request.config')

    @api.model
    def default_get(self, fields):
        res = {}
        active_id = self._context.get('active_id')
        if active_id:
            res = {'config_id': active_id}
        return res

    @api.one
    def run(self):
        ApiCaller(self.config_id).run(self.date)