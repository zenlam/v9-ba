# -*- coding: utf-8 -*-

{

    'name': 'Full Reconciliation Fix',
    'version': '1.0',
    'author': 'ONNET SOLUTIONS SDN BHD',
    'website': 'http://www.on.net.my',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'description': """
    Fix the issue of is_reconciled boolean field not updated.
    """,
    'depends': [
        'account_full_reconcile',
    ],
    'data': [],
    'installable': True,
}
