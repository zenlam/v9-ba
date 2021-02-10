from openerp import fields, models, api, _
import pysftp
from ftplib import FTP
from openerp.exceptions import UserError

class mall_integration_summary_template_config(models.Model):
    _name = 'mall.template.summary.config'

    name = fields.Char('Name')
    active = fields.Boolean(string=_("Active"), default=True)
    prefix = fields.Char('Prefix')
    machine = fields.Char('Machine ID')
    date_format = fields.Char('Date Format', default='%Y%m%d')
    filename_date_format = fields.Char('File Name Date Format', default='%Y%m%d')
    padding = fields.Integer('Padding Sale Number')
    ip = fields.Char('FTP Server')
    port = fields.Integer('Port', default=21)
    gst_padding = fields.Integer('Padding GST Number')
    cash_padding = fields.Integer('Padding Cash Payment')
    other_padding = fields.Integer('Padding Other Payment')
    discount_padding = fields.Integer('Padding Discount Number')
    ticket_count_padding = fields.Integer('Padding Ticket Count Number')
    total_quantity_padding = fields.Integer('Padding Total Quantity Number')
    password = fields.Char('Password')
    outlet_ids = fields.Many2one(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')
    before_gst_padding = fields.Integer('Padding Before GST Number')
    position = fields.Char('Data Format')
    name_file = fields.Char('File Name')
    period = fields.Selection([('daily', 'Daily'), ('monthly', 'Monthly')], default='daily')
    type = fields.Selection([('ftp', 'FTP'), ('sftp', 'SFTP')], default='ftp')
    data_type = fields.Selection([('summary', 'Summary'), ('detail', 'Detail')], default='summary')
    sequence = fields.Integer('Sequence', default=000)
    next_number = fields.Integer('Next Number', default=1)
    last_modified_seq = fields.Date('Last modified seq')
    sequence_padding = fields.Integer('Padding Sequence', default=1)
    passive_mode = fields.Boolean('Passive Mode', default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    client_request = fields.Boolean(string='Client Request', default=False, help='If this is true, system will not '
                                                                                 'transfer the GTO report to the FTP '
                                                                                 'server since the client will request '
                                                                                 'the report.')
    transfer_directory = fields.Char(string='FTP / SFTP Directory', help='Leave this empty if you want to store the file '
                                                                       'in the first directory after login.\n'
                                                                       'Example: Sent\ ')
    file_format = fields.Selection([('daily', 'Daily'), ('hourly', 'Hourly')],
                                   string='File Format', required=1,
                                   default='daily')
    picker_transfer = fields.Boolean(string='Picker Transfer', default=False,
                                     help='Check this if any picker program '
                                          'is installed to transfer the '
                                          'report to the mall server.')

    @api.multi
    def test_connection(self):
        """
        Test connection to server
        @return:
        """
        # This is just temporary, refactor whole module later
        if self.type == 'ftp':
            self.ftp_connect()
        elif self.type == 'sftp':
            self.sftp_connect()
        raise UserError(_("Success !"))

    def ftp_connect(self):
        try:
            ftp = FTP(self.ip)
            if not self.passive_mode:
                ftp.set_pasv(False)
            ftp.connect(self.ip, int(self.port))
            ftp.login(self.machine, self.password)
            ftp.close()
        except Exception as e:
            raise UserError(str(e))

    def sftp_connect(self):
        try:
            ip = self.ip
            username = self.machine
            password = self.password or ''
            port = int(self.port)
            # sftp = SFTPClient(str(ip), str(username), str(password))
            # sftp.upload('/' + str(name_report), str(path_file))
            with pysftp.Connection(ip, username=username, password=password, port=port) as connection:
                connection.listdir()
        except Exception as e:
            raise UserError(str(e))
