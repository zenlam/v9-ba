# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Analytic and Fiscal Position",

    'summary': """
        Analytic Account
        Fiscal Position
        """,

    'description': """
        Append field analytic account to location
    """,

    'author': "HanelSoft",
    'website': "http://hanelsoft.vn",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Warehouse',
    'version': '1.0',

    # any module necessary for this one to work correctly

    'depends': ['sale_stock', 'stock_account', 'purchase', 'account', 'product_expiry'],
    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/br_stock_view.xml',
        'views/br_account_view.xml',
        'views/br_template.xml',
        'views/br_purchase_view.xml',
        'views/br_sale_order_view.xml',
        # 'views/br_location_view.xml'
        # 'security/ir_rule_view.xml'
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
