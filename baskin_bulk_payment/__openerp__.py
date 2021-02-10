# -*- coding: utf-8 -*-

{

    'name': 'Baskin Bulk Payment',
    'version': '1.0',
    'author': 'ONNET SOLUTIONS SDN BHD',
    'website': 'http://www.on.net.my',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'depends': [
        'account_asset',
        'account_cancel',
        'br_analytic_fiscal',
        'br_account',
        'br_base',
        'purchase',
        'web_readonly_bypass',
        'list_view_currency_issue',
    ],
    'data': [
        'security/baskin_bulk_payment_security.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/account_bulk_payment_data.xml',
        'views/templates.xml',
        'views/report_vendor_payment.xml',
        'views/report_vendor_payment_base_currency.xml',
        'views/report_vendor_payment_foreign_currency.xml',
        'views/account_view.xml',
        'views/account_bulk_payment_view.xml',
        'views/account_invoice_view.xml',
        'views/purchase_view.xml',
        'wizard/wizard_payment_remark_view.xml',
        'wizard/wizard_payment_confirm_view.xml',
    ],
    'qweb': [
        'static/src/xml/account_payment.xml',
    ],
    'installable': True,
}
