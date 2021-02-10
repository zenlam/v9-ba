import os
# from sftp_client import SFTPClient
import pysftp
from ftplib import FTP
from openerp import models, fields, _, api
from datetime import datetime, date, timedelta
from openerp import tools
import base64
import traceback

options = tools.config.options
# TODO: Create general configuration for timedelta
d_hour = timedelta(hours=8)


class ftp_gto_summary_report(models.Model):
    _name = 'ftp.gto.summary'

    @api.model
    def ftp_gto_summary_daily(self):
        if 'run_mall_schedule' in options and options['run_mall_schedule'] is True:
            now = datetime.now() + d_hour
            template_ids = self.env['mall.template.summary.config'].search([('period', '=', 'daily'), ('active', '=', True)])
            end_date = now - timedelta(days=1)
            self.run_file_transfer_schedule(template_ids, end_date=end_date)
            request_configs = self.env['br.request.config'].search([('period', '=', 'daily'), ('active', '=', True)])
            self.run_api_transfer(request_configs)

    @api.model
    def ftp_gto_summary_monthly(self):
        if 'run_mall_schedule' in options and options['run_mall_schedule'] is True:
            now = datetime.now() + d_hour
            end_date = now.replace(day=1) - timedelta(days=1)
            start_date = now.replace(month=now.month - 1, day=1) - timedelta(days=1)
            template_ids = self.env['mall.template.summary.config'].search([('period', '=', 'monthly'), ('active', '=', True)])
            self.run_file_transfer_schedule(template_ids, start_date=start_date, end_date=end_date)
            request_configs = self.env['br.request.config'].search([('period', '=', 'monthly'), ('active', '=', True)])
            self.run_api_transfer(request_configs)

    def run_api_transfer(self, configs):
        """Transfer log via vendor api"""
        configs.send_requests()

    @api.model
    def run_file_transfer_xmlrpc(self, param):
        template_id = param.get('template_id', False)
        template = self.env['mall.template.summary.config'].browse(template_id)
        if template:
            if template.period == 'daily':
                now = datetime.now() + d_hour
                end_date = now - timedelta(days=1)
                start_date = None
            else:
                now = datetime.now() + d_hour
                end_date = now.replace(day=1) - timedelta(days=1)
                start_date = now.replace(month=now.month - 1,
                                         day=1) - timedelta(days=1)
        else:
            template = False
        return self.with_context(get_from_client=1).run_file_transfer_schedule(
            template, start_date, end_date)

    def run_file_transfer_schedule(self, template_ids, start_date=None, end_date=None):
        """
        Transfer file to mall's server
        @param template_ids: object (mall.template.summary.config)
        @param start_date: datetime
        @param end_date: datetime
        @return:
        """
        now = datetime.now() + d_hour
        for template_id in template_ids:
            # if last modified sequence not today -> sequence ++
            today = datetime.now().date().strftime('%Y-%m-%d')
            if not template_id.last_modified_seq or \
                            template_id.last_modified_seq != today:
                template_id.last_modified_seq = datetime.now().date()
                template_id.sequence = \
                    template_id.sequence + template_id.next_number

            msg_log = ''
            state = 'done'
            report = self.env['gto.summary.report'].create({'date': end_date,
                                                            'from_date': start_date,
                                                            'outlet_ids': template_id.outlet_ids[0].id})
            result = ''
            name_report = 'unknown.txt'
            if template_id.file_format == 'hourly':
                cash_data = report.get_cash_data_hourly()
                total_hour = 24
                for hour in range(total_hour):
                    cash = cash_data.get(hour, 0)
                    data = self.get_all_data_hourly(report, hour, cash)
                    format = {
                        'prefix': template_id.prefix,
                        'machine': template_id.machine,
                        'date': datetime.strftime(end_date,
                                                  template_id.date_format or '%Y%m%d'),
                        'total': 0,
                        'before_tax': 0,
                        'gst': 0,
                        'discount': 0,
                        'cash': '%%0%s.2f' % (template_id.cash_padding + 3) % (
                                    cash or 0),
                        'ticket_count': 0,
                        'ticket_off_site': 0,
                        'ticket_on_off': 0,
                        'total_quantity': 0,
                        'total_off_quantity': 0,
                        'total_on_off_quantity': 0,
                        'sequence': '%%0%sd' % template_id.sequence_padding % template_id.sequence,
                        'filename_date': datetime.strftime(end_date,
                                                           template_id.filename_date_format or '%Y%m%d'),
                        'hour': '%02d' % hour
                    }
                    if data['on_site_with_tax'] is not None or data[
                        'off_site_with_tax'] is not None:
                        format.update({
                            'total': '%%0%s.2f' % (template_id.padding + 3) %
                                     data['on_site_with_tax'],
                            'total_on_off': '%%0%s.2f' % (
                                        template_id.padding + 3) % (
                                                    data['on_site_with_tax'] +
                                                    data['off_site_with_tax']),
                            'before_tax': '%%0%s.2f' % (
                                        template_id.before_gst_padding + 3) %
                                          data['on_site_without_tax'],
                            'before_tax_on_off': '%%0%s.2f' % (
                                        template_id.before_gst_padding + 3) % (
                                                         data[
                                                             'on_site_without_tax'] +
                                                         data[
                                                             'off_site_without_tax']),
                            'gst': '%%0%s.2f' % (template_id.gst_padding + 3) %
                                   data['on_site_tax'],
                            'gst_on_off': '%%0%s.2f' % (
                                        template_id.gst_padding + 3) % (
                                                  data['on_site_tax'] + data[
                                              'off_site_tax']),
                            'discount': '%%0%s.2f' % (
                                        template_id.discount_padding + 3) % 0,
                            'total_quantity': '%%0%sd' % (
                                    template_id.total_quantity_padding + 3) %
                                              data['onsite_tq'],
                            'total_off_quantity': '%%0%sd' % (
                                    template_id.total_quantity_padding + 3) %
                                               data['offsite_tq'],
                            'total_on_off_quantity': '%%0%sd' % (
                                    template_id.total_quantity_padding + 3) % (
                                                 data['total_tq']),
                            'ticket_count': '%%0%sd' % (
                                        template_id.ticket_count_padding + 3) %
                                            data['onsite_tc'],
                            'ticket_off_site': '%%0%sd' % (
                                        template_id.ticket_count_padding + 3) %
                                               data['offsite_tc'],
                            'ticket_on_off': '%%0%sd' % (
                                        template_id.ticket_count_padding + 3) % (
                                             data['total_tc']),
                            'other': '%%0%s.2f' % (
                                        template_id.other_padding + 3) % (data[
                                                                              'on_site_with_tax'] - cash),
                            'other_on_off': '%%0%s.2f' % (
                                        template_id.other_padding + 3) % (
                                                    data['on_site_with_tax'] +
                                                    data[
                                                        'off_site_with_tax'] - cash),
                            'other_wo_tax': '%%0%s.2f' % (
                                        template_id.other_padding + 3) % (
                                                    data[
                                                        'on_site_without_tax'] -
                                                    data['cash_wo_tax']),
                            'other_wo_tax_on_off': '%%0%s.2f' % (
                                        template_id.other_padding + 3) % (
                                                           data[
                                                               'on_site_without_tax'] +
                                                           data[
                                                               'off_site_without_tax'] -
                                                           data[
                                                               'cash_wo_tax']),
                            'cash_wo_tax': '%%0%s.2f' % (
                                        template_id.cash_padding + 3) % (data[
                                                                             'cash_wo_tax'] or 0)
                        })
                    else:
                        msg_log += 'There are no data in the report! '
                    output = template_id.position.format(**format)
                    output.encode('utf-8', 'ignore')
                    result += (output + '\n')
                    name_report = template_id.name_file.format(
                        **format) + '.txt'
                # if client download report -> don't write file to server
                if not self.env.context.get('get_from_client'):
                    path_file = os.path.abspath(
                        os.path.join(os.path.dirname(__file__),
                                     os.path.pardir)) + '/txt/' + name_report
                    fh = open(path_file, "a")
                    fh.write(result)
                    fh.close()
            else:
                data, cash = self.get_all_data(report)
                format = {
                    'prefix': template_id.prefix,
                    'machine': template_id.machine,
                    'date': datetime.strftime(end_date, template_id.date_format or '%Y%m%d'),
                    'total': 0,
                    'before_tax': 0,
                    'gst': 0,
                    'discount': 0,
                    'cash': '%%0%s.2f' % (template_id.cash_padding + 3) % (cash or 0),
                    'total_quantity': 0,
                    'total_off_quantity': 0,
                    'total_on_off_quantity': 0,
                    'ticket_count': 0,
                    'ticket_off_site': 0,
                    'ticket_on_off': 0,
                    'sequence': '%%0%sd' % template_id.sequence_padding % template_id.sequence,
                    'filename_date': datetime.strftime(end_date, template_id.filename_date_format or '%Y%m%d'),
                    'hour': '%02d' % 0
                }
                if data['on_site_with_tax'] is not None or data['off_site_with_tax'] is not None:
                    format.update({
                        'total': '%%0%s.2f' % (template_id.padding + 3) % data['on_site_with_tax'],
                        'total_on_off': '%%0%s.2f' % (template_id.padding + 3) % (
                                data['on_site_with_tax'] + data['off_site_with_tax']),
                        'before_tax': '%%0%s.2f' % (template_id.before_gst_padding + 3) % data['on_site_without_tax'],
                        'before_tax_on_off': '%%0%s.2f' % (template_id.before_gst_padding + 3) % (
                                data['on_site_without_tax'] + data['off_site_without_tax']),
                        'gst': '%%0%s.2f' % (template_id.gst_padding + 3) % data['on_site_tax'],
                        'gst_on_off': '%%0%s.2f' % (template_id.gst_padding + 3) % (
                                data['on_site_tax'] + data['off_site_tax']),
                        'discount': '%%0%s.2f' % (template_id.discount_padding + 3) % 0,
                        'total_quantity': '%%0%sd' % (template_id.total_quantity_padding + 3) % data['onsite_tq'],
                        'total_off_quantity': '%%0%sd' % (template_id.total_quantity_padding + 3) % data['offsite_tq'],
                        'total_on_off_quantity': '%%0%sd' % (template_id.total_quantity_padding + 3) % (data['total_tq']),
                        'ticket_count': '%%0%sd' % (template_id.ticket_count_padding + 3) % data['onsite_tc'],
                        'ticket_off_site': '%%0%sd' % (template_id.ticket_count_padding + 3) % data['offsite_tc'],
                        'ticket_on_off': '%%0%sd' % (template_id.ticket_count_padding + 3) % (data['total_tc']),
                        'other': '%%0%s.2f' % (template_id.other_padding + 3) % (data['on_site_with_tax'] - cash),
                        'other_on_off': '%%0%s.2f' % (template_id.other_padding + 3) % (
                                data['on_site_with_tax'] + data['off_site_with_tax'] - cash),
                        'other_wo_tax': '%%0%s.2f' % (template_id.other_padding + 3) % (
                                data['on_site_without_tax'] - data['cash_wo_tax']),
                        'other_wo_tax_on_off': '%%0%s.2f' % (template_id.other_padding + 3) % (
                                data['on_site_without_tax'] + data['off_site_without_tax'] - data['cash_wo_tax']),
                        'cash_wo_tax': '%%0%s.2f' % (template_id.cash_padding + 3) % (data['cash_wo_tax'] or 0)
                    })
                else:
                    msg_log += 'There are no data in the report! '
                output = template_id.position.format(**format)
                output.encode('utf-8', 'ignore')
                result += output
                name_report = template_id.name_file.format(**format) + '.txt'
                # if client download report -> don't write file to server
                if not self.env.context.get('get_from_client'):
                    path_file = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)) + '/txt/' + name_report
                    fh = open(path_file, "wb")
                    fh.write(output)
                    fh.close()

            # if client download report -> don't transfer file to server
            if not self.env.context.get('get_from_client') and not template_id.client_request:
                # TODO: Create general interface for connection methods
                if template_id.type == 'ftp':
                    try:
                        ftp = FTP(template_id.ip)
                        if not template_id.passive_mode:
                            ftp.set_pasv(False)
                        ftp.connect(template_id.ip, int(template_id.port))
                        ftp.login(template_id.machine, template_id.password)
                        transfer_directory = template_id.transfer_directory or ''
                        ftp.storbinary("STOR " + transfer_directory + name_report, open(path_file, 'rb'))
                        ftp.close()
                    except Exception as e:
                        msg_log += traceback.format_exc()
                        state = 'except'

                elif template_id.type == 'sftp':
                    try:
                        ip = template_id.ip
                        username = template_id.machine
                        password = template_id.password or ''
                        port = int(template_id.port)
                        transfer_directory = template_id.transfer_directory or ''
                        # sftp = SFTPClient(str(ip), str(username), str(password))
                        # sftp.upload('/' + str(name_report), str(path_file))
                        with pysftp.Connection(ip, username=username, password=password, port=port) as connection:
                            connection.put(str(path_file), str(transfer_directory + name_report))
                    except Exception as e:
                        msg_log += traceback.format_exc()
                        state = 'except'
                try:
                    path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)) + '/txt/'
                    get_list = os.listdir(path)
                    for file in get_list:
                        mtime = os.path.getmtime(path + file)
                        date_create = datetime.fromtimestamp(mtime)
                        if (now - date_create).days > 60:
                            os.remove(path + file)

                except OSError:
                    pass
                actual_file = open(path_file, 'r')
                vals = {
                    'file_name': name_report,
                    'date_transfer': datetime.now(),
                    'state': state,
                    'info': msg_log,
                    'outlet_ids': template_id.outlet_ids[0].id,
                    'company_id': template_id.company_id.id,
                    'file': base64.encodestring(actual_file.read()),
                }
                actual_file.close()
                self.env['log.gto.report'].create(vals)
            # if call from outlet client then return
            if self.env.context.get('get_from_client'):
                return result, name_report

    def get_all_data(self, report):
        """

        @param report: report object (gto.summary.report)
        @return:
        """
        return report.get_onsite_offsite_data(), report.get_cash_data()[0]['cash'] or 0

    def get_all_data_hourly(self, report, hour, cash):
        """
        @param report: report object (gto.summary.report)
        @param hour: get current hour
        @return:
        """
        return report.get_onsite_offsite_data_hourly(hour, cash)
