#!/usr/bin/python
# -*- encoding: utf-8 -*-
{
    'name': "Freeze POS Screen",
    'summary': """
       Freeze POS Screen
        """,
    'description': """
            Freeze screen after 1 mins if there's no action on POS screen, require user to log in using PIN code
    """,
    'author': "Elephas",
    'website': "http://elephas.vn",
    'category': 'Point Of Sale',
    'version': '1.0',
    'depends': ['br_point_of_sale'],
    'data': [
        'views/templates.xml',
        'views/pos_config_settings.xml',
    ],
    'qweb': [],
    'application': True,
    "installable": True,
    'auto_install': False,

}
