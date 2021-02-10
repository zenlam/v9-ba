# -*- coding: utf-8 -*-
{
    'name': 'Baskin Robbin Partner ID',
    'version': '1.0',
    'author': 'Onnet Solution SDN BHD',
    'website': 'http://www.onnet.my',
    'description': '''
    Assign a unique sequence number to every partner.
    Make street, city, state, zip, country, business registration no, phone and saleperson fields mandatory.

    ''',
    'depends': ['account',
                'sale',
                'base',
                'crm'],
    'data': [
            'views/res_config_view.xml',
            'views/sale_view.xml',
            'views/res_partner_view.xml',
            ],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
