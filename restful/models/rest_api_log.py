# -*- coding: utf-8 -*-

from openerp import api, fields, models
import requests
from ast import literal_eval
from openerp.addons.connector.queue.job import (
    job
)
from openerp import tools

options = tools.config.options

@job
def _recall_api(session, model_name, rec_id, func):
    record = session.env[model_name].browse(rec_id)
    if record:
        getattr(record, func)()


class RestApiLog(models.Model):
    _name = "rest.api.log"
    _description = "Log file for REST API Calling"
    _order = "request_time desc"

    request_method = fields.Char(string='Request Method')
    request_url = fields.Char(string='Request URL')
    request_headers = fields.Char(string='Request Headers')
    request_params = fields.Char(string='Request Params')
    request_response = fields.Char(string='Request Response')
    request_uid = fields.Many2one('res.users', string='Request User')
    request_status = fields.Char(string='Request Status')
    request_time = fields.Datetime(string='Request Time')
    request_arguments = fields.Char(string='Request Arguments')
    request_direction = fields.Selection([('incoming', 'Incoming'),
                                          ('outgoing', 'Outgoing')],
                                         string='Direction',
                                         default='incoming',
                                         required=1)
    request_result = fields.Char(compute='get_request_result',
                                 string='Request Result',
                                 store=True)
    current_retry = fields.Integer(string='Number of Retry', default=-1)

    @api.multi
    def run(self):
        if 'rest_api_outgoing' in options and options['rest_api_outgoing']:
            company = self.env.user.company_id
            for rec in self:
                status_code = 0
                number_of_attempts = company.api_attempts_count
                count = 0
                while status_code != 200:
                    if rec.request_method == 'GET':
                        try:
                            p = requests.get(url=rec.request_url,
                                             data=literal_eval(rec.request_arguments),
                                             headers=literal_eval(rec.request_headers))
                            rec.request_status = p.status_code
                            rec.request_response = p.content
                            status_code = p.status_code
                        except Exception as e:
                            rec.request_status = '400'
                            rec.request_response = e
                    elif rec.request_method == 'POST':
                        try:
                            p = requests.post(url=rec.request_url,
                                              data=literal_eval(rec.request_arguments),
                                              headers=literal_eval(rec.request_headers))
                            rec.request_status = p.status_code
                            rec.request_response = p.content
                            status_code = p.status_code
                        except Exception as e:
                            rec.request_status = '400'
                            rec.request_response = e
                    elif rec.request_method == 'PUT':
                        try:
                            p = requests.put(url=rec.request_url,
                                             data=literal_eval(rec.request_arguments),
                                             headers=literal_eval(rec.request_headers))
                            rec.request_status = p.status_code
                            rec.request_response = p.content
                            status_code = p.status_code
                        except Exception as e:
                            rec.request_status = '400'
                            rec.request_response = e
                    rec.current_retry += 1
                    count += 1
                    if count <= number_of_attempts:
                        continue
                    else:
                        break

    @api.depends('request_response')
    def get_request_result(self):
        """ Get the request result """
        for rec in self:
            if rec.request_response:
                try:
                    if rec.request_direction == 'incoming':
                        rec.request_result = ''
                    else:
                        rec.request_result = '-1'
                        response = literal_eval(rec.request_response)
                        if response.get('code'):
                            rec.request_result = response.get('code')
                except Exception as e:
                    pass

