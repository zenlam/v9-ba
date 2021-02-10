# -*- coding: utf-8 -*-

{
    'name': 'Baskin Stock Count Receipt Report',
    'version': '1.0',
    'category': 'Stock',
    'description': '''''',
    'author': 'Onnet',
    'website': '',
    'depends': ['stock','br_inventory_adjustment'],
    'data': [
        'security/ir.model.access.csv',
        'report/stock_count_report.xml',
        'report/pre_stock_count_report.xml',
        'wizard/stock_count_receipt_wizard_view.xml'
    ],
    'installable': True
}
