# -*- coding: utf-8 -*-

{
    'name': 'Baskin Reverse Transfer Reason Category',
    'version': '1.0',
    'category': '',
    'description': '''''',
    'author': 'Onnet',
    'website': '',
    'depends': ['base','stock','br_stock_rebase'],
    'data': [
        'security/ir.model.access.csv',
        'views/reverse_transfer_reason_category_view.xml',
        'views/stock_picking_type_view.xml',
        'wizard/stock_return_picking_view.xml',
        'views/stock_picking_view.xml'
    ],
    'installable': True
}
