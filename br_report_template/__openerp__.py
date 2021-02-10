# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Report Templates",
    'summary': """
            Baskin Robbin Report Templates
        """,

    'description': """

    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Product',
    'version': '1.0',
    'depends': ['sale', 'purchase', 'account'],
    'data': [
        'templates/sale_report.xml',
        'templates/purchase_order.xml',
        'templates/tax_invoice.xml',
        'templates/tax_invoice_approval.xml',
        'views/sale_order.xml',
        'views/purchase_order.xml',
        'views/tax_invoice.xml',
        'views/report_view.xml',
        'views/res_currency.xml'
    ],
    'demo': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
