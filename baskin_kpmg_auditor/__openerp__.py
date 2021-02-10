# -*- coding: utf-8 -*-


{
    'name': 'Baskin KPMG Auditor',
    'version': '1.0',
    'author': 'Onnet Solution SDN BHD',
    'website': 'http://www.onnet.my',
    'description': '''
    ''',
    'depends': ['base','account','mail','calendar','baskin_credit_note','account_voucher','baskin_bulk_payment','account_voucher', 'br_inventory_adjustment'],
    'data': [
            'security/security.xml',
            'views/kpmg_menu.xml',
            'security/ir.model.access.csv',
            'views/bulk_payment_view.xml',
            'views/stock_inventory.xml',
            ],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
