# -*- coding: utf-8 -*-

{

    'name': 'Baskin Bulk Invoice Draft Cancel',
    'description': """
Allows to bulk cancel and redraft account invoices.
====================================

This module adds 'Cancel Invoices' and 'Cancel & Redraft Invoices' action on the tree view of account invoice.
Hence, the user is able to set multiple invoices to 'Cancel' or 'Draft' state.
    """,
    'version': '1.0',
    'author': 'ONNET SOLUTIONS SDN BHD',
    'website': 'http://www.on.net.my',
    'category': 'Accounting',
    'depends': [
        'account_cancel',
        'br_account',
    ],
    'data': [
        'views/account_invoice_view.xml',
    ],
    'installable': True,
}
