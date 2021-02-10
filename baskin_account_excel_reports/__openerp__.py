# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Baskin Account Excel Reports',
    'version': '1.1',
    'summary': 'Baskin Account Excel Reports',
    'author': "ONNET SOLUTIONS SDN BHD",
    'sequence': 30,
    'description': """""",
    'website': 'http://www.on.net.my',
    'depends': [
        'account',
        'account_accountant',
        'br_multi_outlet',
        'baskin_excel_direct',
        'analytic',
        'br_stock'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/ir_cron.xml',
        'data/data.xml',
        'views/baskin_account_excel_menu_view.xml',
        'views/stock_view.xml',
        'wizard/general_ledger_report_view.xml',
        'views/gl_consolidation_config_view.xml',
        'views/gl_consolidation_log_view.xml',
        # 'views/account_view.xml',
        'views/analytic_view.xml',
        'views/analytic_group_view.xml',
        'wizard/account_financial_report_view.xml',
        'wizard/balance_sheet_report_view.xml',
        'wizard/trial_balance_report_view.xml',
        'wizard/balance_sheet_report_view.xml',
        'reports/journal_entry_report.xml'
    ],
    'installable': True,
    'application': True,
}
