# -*- coding: utf-8 -*-
{
    'name': "Analytic Accounts Hierarchy",

    'summary': """
        Analytic Accounts Hierarchy Module
    """,

    'description': """
        Create Tree (Hierarchy) view for Analytic Accounts and compute the Child balances to the Parent.
        You have to enable the Analytic Accounting for each users at Settings > Users first.

        Demo user: demo
        Password: demo
    """,

    'author': "Farrell Rafi",
    'website': "http://odooabc.com",

    'live_test_url': 'http://odooabc.com:90/web?db=hierarchy',
    'license': "Other proprietary",
    'price': 100.00,
    'currency': 'USD',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '0.1',

    'images': [
        'images/screenshot.png',
    ],

    # any module necessary for this one to work correctly
    'depends': ['account_accountant'],

    # always loaded
    'data': [
        'views/analytic.xml',
        'views/list.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
}
