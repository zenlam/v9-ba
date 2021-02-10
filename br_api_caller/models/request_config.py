from openerp import fields, models, api, tools, _
import config
from datetime import datetime
from api_caller import ApiCaller
import ast


def str2tuple(s):
    return eval('tuple(%s)' % (s or ''))


class RequestConfig(models.Model):
    _name = 'br.request.config'
    _order = 'name'

    name = fields.Char(_("Name"))
    is_async = fields.Boolean(_("Asynchronous"), default=False)
    active = fields.Boolean(_("Active"), default=True)
    request_ids = fields.One2many(comodel_name='br.request.details', inverse_name='config_id')

    @api.multi
    def send_requests(self, *args, **kwargs):
        for conf in self:
            ApiCaller(conf).run(*args, **kwargs)

    def get_logger(self):
        self.ensure_one()
        return self.env['br.request.log'].create({'config_id': self.id, 'name': datetime.now().strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)})


class RequestDetails(models.Model):
    _name = 'br.request.details'
    _order = 'sequence ASC, name ASC'

    name = fields.Char("Name")
    url = fields.Char(_("URL"))
    request_method = fields.Selection(selection=config.REQUEST_METHODS, default='post', string=_("Request Method"))
    sequence = fields.Integer(_("Sequence"))
    timeout = fields.Integer(_("Timeout(s)"), default=60)
    # model = fields.Char(string=_("Object"))
    func_name = fields.Char(string=_("Method"))
    func_args = fields.Char(string=_("Arguments"),default='')
    config_id = fields.Many2one(comodel_name='br.request.config')
    use_fixed_data = fields.Boolean(string=_("Use Fixed Data"), default=True)
    header_ids = fields.One2many(comodel_name='br.request.details.header', inverse_name='request_id', string=_("Header Information"))
    fixed_request_body = fields.Text(string=_("Request Body"), default="[]")

    @api.one
    @api.constrains('func_args')
    def _check_args(self):
        """Make sure that arguments is placed in tuple"""
        try:
            str2tuple(self.func_args)
        except Exception:
            return False
        return True

    def normalize_body_data(self, str):
        """
        input data from string may not eval-able
        @param str: string
        @return:
        """
        return str.replace('\n', '').replace('true', 'True').replace('false', 'False')

    def get_request_body(self, *args, **kwargs):
        """

        @return: list - request's body
        """
        self.ensure_one()
        request_body = ''
        if self.use_fixed_data:
            request_body = ast.literal_eval(self.normalize_body_data(self.fixed_request_body)) if self.fixed_request_body else ''
        else:
            # Get dynamic params
            func = self._params_func()
            if func:
                if not args:
                    args = tuple(self.func_args or '')
                request_body = func(*args, **kwargs)
        return request_body

    def get_request_headers(self):
        """

        @return: dict - request's header
        """
        self.ensure_one()
        headers = {}
        for h in self.header_ids:
            headers[h.name] = h.value
        return headers

    def _params_func(self):
        """

        @return: function - function that will be used to get dynamic params
        """
        func = getattr(self, self.func_name)
        return func



class RequestHeader(models.Model):
    _name = 'br.request.details.header'

    name = fields.Char(_("Name"), required=True)
    value = fields.Char(_("Value"))
    request_id = fields.Many2one(comodel_name='br.request.details')
