# -*- coding: utf-8 -*-

{

    'name': 'Baskin Hide Change Menu Button',
    'version': '1.0',
    'author': 'ONNET SOLUTIONS SDN BHD',
    'website': 'http://www.on.net.my',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'depends': [
        'account_voucher',
        'analytic',
        'br_base'
    ],
    'data': [
        'security/br_hide_show_security.xml',
        'views/account_view.xml',
        'views/analytic_view.xml',
    ],
    'installable': True,
 }
