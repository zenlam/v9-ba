# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Stock Location Flush",

    'summary': """
    Move all product from location to another
        """,
    'description': """
    Move all product from location to another
    """,
    'author': "LongDT",
    'website': "http://elephas.vn",
    'category': 'Warehouse',
    'version': '1.0',
    'depends': [
        'stock',
        'br_stock',
        # 'br_multi_outlet'
    ],
    'data': [
        'views/stock_location_flush.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
