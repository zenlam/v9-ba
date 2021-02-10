#!/usr/bin/python
# -*- encoding: utf-8 -*-
{
    'name': "Tax Adjustment for Pos Order",
    'summary': """
        Tax Adjustment for Pos Order
        """,
    'description': """
        Tax Adjustment for Pos Order
    """,
    'author': "Elephas",
    'website': "http://www.elephas.vn/",
    'category': 'Point Of Sale',
    'version': '1.0',
    'depends': ['br_point_of_sale'],
    'data': [
        'views/pos_order_view.xml',
        'views/res_company.xml'
    ],
    'qweb': [
            ],
    'application': True,
    "installable": True,
    'auto_install': False,

}
