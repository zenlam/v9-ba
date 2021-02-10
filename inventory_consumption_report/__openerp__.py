# -*- coding: utf-8 -*-

{
    'name': 'Inventory Consumption Report',
    'version': '1.0',
    'category': 'stock',
    'description': '''''',
    'author': 'Onnet',
    'website': '',
    'depends': ['stock','br_consumable_stock_flag', 'baskin_stock_flush'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'wizard/inventory_consumption_view.xml',
        'views/consumption_transaction_type_view.xml'
    ],
    'installable': True
}
