#!/usr/bin/python
# -*- encoding: utf-8 -*-
# copyright: HanelSoft Co

{
    'name': "Baskin Robbins Point Of Sale",

    'summary': """
        Baskin Robbins Point Of Sale
        """,

    'description': """
        Baskin Robin Point Of Sale.
        This module is based on Point of Sale Module.
    """,

    'author': "Hanelsoft/TruongNN",
    'website': "http://hanelsoft.vn",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Point Of Sale',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['br_multi_outlet', 'br_product', 'br_pricelist', 'br_stock_rebase', 'br_point_of_sale_rebase', 'br_account', 'report',
                'web_widget_color'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/point_of_sale_view.xml',
        'views/pos_session.xml',
        'views/br_pos.xml', # loading *.js, *.css
        'views/e_wallet_platform_views.xml',
        'views/account_tax.xml',
        'views/point_of_sale_dashboard.xml',
        'views/pos_company.xml',
        'views/terminal.xml',
        'views/pos_session_signout_confirm.xml',
        'views/account_journal_view.xml',
        'wizard/pos_payment.xml',
        'reports/sales_raw_data.xml',
        'reports/pos_sales_by_order.xml',
        'reports/pos_sales_by_product.xml',
        'reports/pos_sales_by_menuname.xml',
        'reports/report_receipt.xml',
        'reports/report_paperfomat.xml',
        'reports/x_report.xml',
        'reports/z_report.xml',
        'reports/pre_closing_report.xml'
    ],
    'qweb': ['static/src/xml/br_pos.xml',
             'static/src/xml/br_report_receipt.xml',
            ],
    'application': True,
    "installable": True,
    'auto_install': False,

}
