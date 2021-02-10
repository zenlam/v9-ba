# -*- coding: utf-8 -*-
{
    'name': 'Baskin Robbin Product Qty',
    'summary': '''
            Baskin Robbin Product Qty
    ''',
    'description': '''
    ''',
    'author': 'Onnet Solution SDN BHD',
    'website': 'http://www.onnet.my',
    'category': 'Stock',
    'version': '0.1',
    'depends': ['product', 'stock', 'baskin_stock_flush'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/product_qty_onhand_check_wizard_view.xml',
        'view/stock_view.xml',
    ],
    'application': True,
    'installable': True,
}
