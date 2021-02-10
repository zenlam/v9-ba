# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'COT Hierarchy',
    'version' : '1.1',
    'summary': 'COT Hierarchy',
    'author' : "ONNET SOLUTIONS SDN BHD",
    'sequence': 30,
    'description': """ Chart of Taxes with hierarchy.
This module create parent and child relation in account""",
    'category' : 'Accounting & Finance',
    'website': 'http://www.on.net.my',
    'depends' : ['account', 'account_accountant'],
    'data': [
        'security/account_cot_security.xml',
        'security/ir.model.access.csv',
        'views/account_tax_view.xml',
        'views/account_account_view.xml',
        'wizard/chart_of_tax_wizard_view.xml',
        'wizard/chart_of_account_wizard_view.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
