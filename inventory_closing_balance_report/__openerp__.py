# -*- coding: utf-8 -*-

{
    'name': 'Inventory Closing Balance Report',
    'version': '1.0',
    'category': 'stock',
    'description': '''''',
    'author': 'Onnet',
    'website': '',
    'depends': ['stock', 'br_multi_outlet', 'baskin_stock_flush'],
    'data': [
        'wizard/stock_inventory_closing_balance_view.xml',
        'views/stock_view.xml'
    ],
    'installable': True
}
