# -*- coding: utf-8 -*-


{
    'name': 'Baskin Partner Aged Report',
    'version': '1.0',
    'author': 'Onnet Solution SDN BHD',
    'website': 'http://www.onnet.my',
    'description': '''
    ''',
    'depends': ['account',
                'baskin_excel_direct',
                'baskin_account_excel_reports',
                'report_xlsx'],
    'data': [
            'wizard/account_report_aged_partner_balance_new_view.xml',
            'wizard/report_agedpartnerbalance.xml',
            'report/report_partner_balance.xml'
            ],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
