# -*- coding: utf-8 -*-


{
    'name': 'Baskin credit note',
    'version': '1.0',
    'author': 'Onnet Solution SDN BHD',
    'website': 'http://www.onnet.my',
    'description': '''
    ''',
    'depends': ['baskin_bulk_payment'],
    'data': [
            'wizard/invoice_matching_view.xml',
            'views/account_invoice_view.xml',
            'views/res_company_view.xml',
            ],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
