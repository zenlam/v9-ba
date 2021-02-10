# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Stock Account",
    'summary': """
            Baskin Robbin Stock Account
        """,

    'description': """
        Baskin Robbin Stock Account
    """,
    'author': "Elephas",
    'website': "http://Elephas.vn",
    'category': 'Account',
    'version': '0.1',
    'depends': ['br_stock', 'br_account', 'stock_account'],
    'data': [
        'views/stock_inventory.xml',
        'views/product_view.xml',
        'views/product_data.xml',
    ],
    'demo': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
