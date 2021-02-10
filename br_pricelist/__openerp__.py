# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbins Pricelist",
    'summary': """
            Baskin Robbin Pricelist
        """,

    'description': """

    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Product',
    'version': '0.1',
    'depends': ['br_product'],
    'data': [
        # 'security/ir.model.access.csv',
        # 'security/ir_model_access.xml',
        'security/security.xml',
        'views/pricelist.xml',
        'views/product.xml'
    ],
    'demo': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
