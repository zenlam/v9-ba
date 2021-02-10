# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Stock Picking Wave",

    'summary': """
        Display menu Picking Wave, remove group no one in this menu
        When Done Picking wave, qty done of product must fill
        """,
    'description': """
         Display menu Picking Wave, remove group no one in this menu
         When Done Picking wave, qty done of product must fill
    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Warehouse',
    'version': '1.0',
    'depends': ['stock', 'stock_picking_wave'],
    'data': [
        'views/stock_picking_wave.xml'
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
