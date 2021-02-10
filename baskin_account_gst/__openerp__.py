# -*- coding: utf-8 -*-

{

    'name': 'Baskin Account GST',
    'version': '1.0',
    'author': 'ONNET SOLUTIONS SDN BHD',
    'website': 'http://www.on.net.my',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'depends': [
        'account'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/account_gst_security.xml',
        'views/menuitem_view.xml',
        'views/account_view.xml',
        'wizard/wizard_gst_report_view.xml',
    ],
    'installable': True,
 }
