# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Outlets/Warehouses Permission",

    'summary': """
        Add view permission on outlets and warehouses per user
        """,
    'description': """
        Add view permission on outlets and warehouses per user
    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Warehouse',
    'version': '1.0',
    'depends': ['br_multi_outlet', 'stock', 'br_stock_request'],
    'data': [
        'views/res_users.xml',
        'views/stock_warehouse.xml',
        'views/stock.xml',
        'views/br_pos.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
