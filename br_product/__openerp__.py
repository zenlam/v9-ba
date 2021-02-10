# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Product Menu",
    'summary': """
            Baskin Robbin product master data
        """,

    'description': """

    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Product',
    'version': '0.1',
    'depends': ['base', 'product', 'br_multi_outlet', 'br_uom', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_menu.xml',
        'views/menu_category.xml',
        'menuitems.xml',
        'views/template.xml',
        'data/data.xml',
        'views/product_list.xml'
    ],
    'demo': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
