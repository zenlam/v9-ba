from openerp import models, api, fields, _
import glob
import datetime
import os, platform
from openerp.exceptions import UserError
import subprocess
import base64
import re


def get_parent_directory():
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    result = parent_dir.split(os.sep)[:-1]
    return os.sep.join(result)


class RestorationConfig(models.Model):
    _name = 'restoration.config'

    name = fields.Char(string="Name")
    dest_ip_address = fields.Char(string="Destination Server IP")
    dest_port_no = fields.Char(string="Destination Port Number")
    dest_username = fields.Char(string="Destination Login Username")
    su_password = fields.Char(string="Destination Superuser Password", help="Kindly provide the superuser password for "
                                                                            "sudo command.")
    source_dump_path = fields.Char(string="Source Dump File Path")
    default_dump_file_name = fields.Char(string="Default Source Dump File Name")
    dest_dump_path = fields.Char(string="Destination Dump File Path")
    dest_db_user = fields.Char(string="Destination Database User")
    remove_old = fields.Boolean('Remove Old Database?', help="WARNING: If this is checked, all the old databases which "
                                                             "are owned by the same database user will be dropped.",
                                default=False)
    remove_dump = fields.Boolean('Remove Dump File?', help="If this is checked, the copied dump file will be removed"
                                                           " after the restoration.", default=False)
    db_name_prefix = fields.Char(string='Database Name Prefix', help="This prefix must be same as the db-filter from "
                                                                     "config file. If no prefix is provided, the "
                                                                     "database name will be exactly same as the dump "
                                                                     "file name.")
    active = fields.Boolean('Active?', default=True)
    state = fields.Selection([('draft', 'Draft Configuration'), ('not_connected', 'Not Connected'),
                              ('connected', 'Established Connection')], 'Status', default='draft', copy=False)
    latest_db = fields.Boolean('Restore Latest Database?', default=True,
                               help="If this is checked, the latest database dump file in 'Source Dump File Path' will"
                                    " be automatically determined and restored. Else, the default dump file will be "
                                    "restored.")
    log_directory = fields.Char('Log File Directory', help="Provide a directory to store the log file.",
                                default=lambda self: self.get_default_log_directory())
    sql_query = fields.Text('SQL Query', help="Write the query for the restored database to disable services or update"
                                              " data. Kindly ensure the query ends with ';'.")

    @api.multi
    def restore(self, redo):
        """
        perform the database restoration on the destination server
        :param redo: True if the previous restoration has failed and desires to restore again
        :return:
        """
        brl = self.env['restoration.log']
        copy_script_path = get_parent_directory() + "/copy.sh"
        restore_script_path = get_parent_directory() + "/restore.sh"

        self.check_connection()
        if self.state == 'connected':
            new_log = brl.create({
                'filename': self.generate_log_file_name(),
                'date_restore': datetime.datetime.now()
            })
            if self.latest_db:
                self.get_latest_dump_file()
            args = ['bash', copy_script_path, self.dest_ip_address, self.dest_port_no, self.dest_username,
                    self.get_full_source_path(), self.dest_dump_path, self.dest_db_user, self.get_db_name(),
                    self.get_dest_file_path(), str(self.remove_old).lower(), restore_script_path,
                    str(self.remove_dump).lower(), self.get_sql_query(), str(redo).lower(), self.su_password]

            log_file_path = self.get_log_path()
            if not os.path.exists(os.path.dirname(log_file_path)):
                os.makedirs(os.path.dirname(log_file_path))
            log_file = open(log_file_path, 'a+')

            try:
                output = subprocess.check_output(args, stderr=subprocess.STDOUT)
                log_file.write(output)
            except subprocess.CalledProcessError as exc:
                log_file.write("Return Code: {0}\n{1}".format(exc.returncode, exc.output))
                new_log.write({
                    'state': 'fail'
                })
            else:
                new_log.write({
                    'state': 'done'
                })
            finally:
                log_file.close()
            log_file = open(log_file_path, 'r')
            new_log.write({
                'name': self.name + datetime.datetime.now().strftime("_%m_%d_") + log_file_path.split('/')[-1].split('.')[0].split('_')[-1],
                'file': base64.encodestring(log_file.read())
            })
            log_file.close()

    @api.multi
    def normal_restoration(self):
        """
        call the restore function with no redo (no failure restoration before)
        :return:
        """
        self.ensure_one()
        self.restore(False)

    @api.multi
    def redo_restoration(self):
        """
        call the restore function with redo option (after failure restoration)
        :return:
        """
        self.ensure_one()
        self.restore(True)

    @api.model
    def auto_restore(self):
        """
        Cron job to call restore function
        :return:
        """
        configurations = self.search([('active', '=', True)])

        if configurations:
            for config in configurations:
                config.restore(False)

    @api.model
    def get_default_log_directory(self):
        default_dir = get_parent_directory().split(os.sep)[:-2]
        default_dir.append('db_restore_log')
        return os.sep.join(default_dir)

    @api.model
    def get_latest_dump_file(self):
        """
        check the given dump file directory to determine the latest dump file that will be used for database restoration
        :return:
        """
        directory = self.source_dump_path + '/*.dump'
        list_of_dump = glob.glob(directory)
        latest_dump = max(list_of_dump, key=os.path.getctime)
        self.default_dump_file_name = latest_dump.split('/')[-1]

    @api.model
    def get_dest_file_path(self):
        result = ""
        if self.default_dump_file_name and self.dest_dump_path:
            file_path = self.dest_dump_path.split('/')
            file_path.append(self.default_dump_file_name)
            result = '/'.join(file_path)
        return result

    @api.model
    def get_db_name(self):
        result = ""
        if self.db_name_prefix:
            new_name = self.db_name_prefix.split('_')
            day_position = 2
            month_position = 1
            if bool(re.search(r'(\d+_\d+_\d+)', self.default_dump_file_name)):
                date = re.search(r'(\d+_\d+_\d+)', self.default_dump_file_name).group().split('_')
                new_name.extend((date[day_position], date[month_position]))
                if "" in new_name:
                    new_name.remove("")
                result = '_'.join(new_name)
        else:
            result = self.default_dump_file_name.split('.')[0]
        return result

    @api.model
    def get_valid_log_path(self):
        """
        Convert the given log directory to a valid format
        :return:
        """
        result = ""
        if self.log_directory:
            dir_name = self.log_directory.split('/')
            if dir_name[-1] == "":
                dir_name.pop()
            result = '/'.join(dir_name)
        return result

    @api.model
    def get_log_path(self):
        result = ""
        if self.log_directory:
            result = self.get_valid_log_path() + '/' + self.generate_log_file_name()
        return result

    @api.model
    def generate_log_file_name(self):
        count = 1
        date = datetime.datetime.now().strftime("_%m_%d_")
        result = self.name + date + 'db_restore_' + str(count) + '.txt'
        while os.path.isfile(self.get_valid_log_path() + '/' + result):
            count += 1
            result = self.name + date + 'db_restore_' + str(count) + '.txt'
        return result

    @api.model
    def get_full_source_path(self):
        return self.source_dump_path + '/' + self.default_dump_file_name

    @api.model
    def get_sql_query(self):
        if self.sql_query:
            result = self.sql_query
        else:
            result = "no_query"
        return result

    @api.multi
    def check_connection(self):
        """
        Check the connection to the destination server
        :return:
        """
        check_conn_script_path = get_parent_directory() + "/check_connection.sh"
        args = ['bash', check_conn_script_path, self.dest_ip_address, self.dest_port_no, self.dest_username]
        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            print(exc.returncode, exc.output)
            self.write({'state': 'not_connected'})
        else:
            self.write({'state': 'connected'})
            print(output)


class KeyAuthenticationConfiguration(models.TransientModel):
    _name = 'key.authentication.configuration'

    dest_ip_address = fields.Char(string="Destination Server IP", default=lambda self: self.get_dest_ip_address())
    dest_port_no = fields.Char(string="Destination Port Number", default=lambda self: self.get_dest_port_no())
    dest_username = fields.Char(string="Destination Login Username", default=lambda self: self.get_dest_username())
    dest_pass = fields.Char(string="Destination Login Password")

    @api.model
    def get_dest_ip_address(self):
        active_id = self.env.context.get('active_id', False)
        if active_id:
            dest_ip_address = self.env['restoration.config'].browse(active_id).dest_ip_address
            if dest_ip_address:
                return dest_ip_address

    @api.model
    def get_dest_port_no(self):
        active_id = self.env.context.get('active_id', False)
        if active_id:
            dest_port_no = self.env['restoration.config'].browse(active_id).dest_port_no
            if dest_port_no:
                return dest_port_no

    @api.model
    def get_dest_username(self):
        active_id = self.env.context.get('active_id', False)
        if active_id:
            dest_username = self.env['restoration.config'].browse(active_id).dest_username
            if dest_username:
                return dest_username

    @api.multi
    def action_establish_connection(self):
        """
        Establish a public key authentication with the given details and credentials
        :return:
        """
        active_id = self.env.context.get('active_id', False)
        res = self.env['restoration.config'].browse(active_id)
        bash_script = get_parent_directory() + "/key_share.sh"
        args = ['bash', bash_script, self.dest_ip_address, self.dest_port_no, self.dest_username, self.dest_pass]
        try:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            print("Status : FAIL", exc.returncode, exc.output)
            raise UserError(_('Not able to establish connection. Kindly ensure the details are provided correctly.'))
        else:
            print(output)
            res.write({'state': 'connected'})


class RestorationLog(models.Model):
    _name = "restoration.log"
    _order = 'id desc'

    name = fields.Char('Record Name', readonly=True)
    filename = fields.Char('File Name')
    file = fields.Binary('File to Download', readonly=True)
    date_restore = fields.Datetime('Date Restore')
    state = fields.Selection([('done', 'Done'), ('fail', 'Fail')], 'State')
