# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin POS Refund",
    'summary': """
            Baskin Robbin POS Refund
        """,

    'description': """

    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Point Of Sale',
    'version': '0.1',
    'depends': ['br_discount'],
    'data': [
        'data/groups.xml',
        'views/pos_refund.xml',
        'wizard/pos_order_refund_process.xml',
    ],
    'demo': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
