# -*- coding: utf-8 -*-


{
    'name': 'Baskin Cake Ordering',
    'version': '1.0',
    'author': 'Onnet Solution SDN BHD',
    'website': 'http://www.onnet.my',
    'description': '''
    ''',
    'depends': ['stock','purchase','point_of_sale','mrp'],
    'data': [
            'security/ir.model.access.csv',
            'security/security.xml',
            'views/cake_ordering_view.xml',
            'views/stock_view.xml',
            'views/stock_move_report_view.xml',
            ],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
