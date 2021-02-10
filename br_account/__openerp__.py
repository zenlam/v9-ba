# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Accounting",

    'summary': """
        Baskin Robbin Accounting Customize
        """,

    'description': """
        Baskin Robbin Accounting Customize
    """,

    'author': "HanelSoft",
    'website': "http://hanelsoft.vn",
    'category': 'Accounting',
    'version': '1.0',
    'depends': ['sale', 'account_asset', 'subscription'],
    'data': [
        'security/account_security.xml',
        'views/account_payment.xml',
        'views/account_invoice.xml',
        'views/asset_account_type.xml',
        'views/account_view.xml',
        'views/account_analytic_view.xml',
        'views/account_subscription_view.xml',


    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
