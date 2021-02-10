# -*- coding: utf-8 -*-
# Copyright 2015 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from cStringIO import StringIO

from openerp.report.report_sxw import report_sxw
from openerp.api import Environment

import logging
_logger = logging.getLogger(__name__)




class ReportTxt(report_sxw):

    def create(self, cr, uid, ids, data, context=None):
        self.env = Environment(cr, uid, context)
        report_obj = self.env['ir.actions.report.xml']
        report = report_obj.search([('report_name', '=', self.name[7:])])
        if report.ids:
            self.title = report.name
            if report.report_type == 'txt':
                return self.create_txt_report(ids, data, report)
        return super(ReportTxt, self).create(cr, uid, ids, data, context)

    def create_txt_report(self, ids, data, report):
        self.parser_instance = self.parser(
            self.env.cr, self.env.uid, self.name2, self.env.context)
        objs = self.getObjects(
            self.env.cr, self.env.uid, ids, self.env.context)
        self.parser_instance.set_context(objs, data, ids, 'txt')
        file_data = StringIO()
        # file = open("newfile.txt", "w")
        self.generate_txt_report(file_data, report, objs)
        # file.close()
        file_data.seek(0)
        return (file_data.read(), 'txt')

    def get_workbook_options(self):
        return {}

    def generate_txt_report(self, report, data, objs):
        # inherit this function and can change file txt name by data.name
        raise NotImplementedError()
