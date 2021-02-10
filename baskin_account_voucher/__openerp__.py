# -*- coding: utf-8 -*-

{

    'name': 'Baskin Account Voucher',
    'version': '1.0',
    'author': 'ONNET SOLUTIONS SDN BHD',
    'website': 'http://www.on.net.my',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'depends': [
        'account_voucher'
    ],
    'data': [
        'security/baskin_account_voucher_security.xml',
        'data/baskin_account_voucher_data.xml',
        'views/account_journal_view.xml',
        'views/account_voucher_view.xml',
        'views/basking_account_voucher_report.xml',
        'views/report_payment_voucher.xml'
    ],
    'installable': True,
 }
