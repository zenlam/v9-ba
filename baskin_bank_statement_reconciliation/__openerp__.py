# -*- coding: utf-8 -*-

{

    'name': 'Baskin Bank Statement Reconciliation',
    'version': '1.0',
    'author': 'ONNET SOLUTIONS SDN BHD',
    'website': 'http://www.on.net.my',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'depends': [
        'account',
        'account_full_reconcile',
        'web_readonly_bypass',
        'baskin_bulk_payment'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/bank_reconcile_data.xml',
        'views/bank_statement_reconcile.xml',
        'views/templates.xml',
        'views/res_company_view.xml',
        'report/bank_reconcile_report.xml',
        'wizard/bank_validate_wizard.xml'
    ],
    'installable': True,
}
