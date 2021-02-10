# -*- coding: utf-8 -*-

{

    'name': 'Baskin Analytic Hierachy',
    'description': """
This module add Chart of Analytic wizard, allow user to filter analytic by date
""",

    'version': '1.0',
    'author': 'Elephas',
    'website': 'http://elephas.vn',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'depends': [
        'analytic',
        'analytic_hierarchy',
        # FIXME: It's kind of weird since we need to depend this module just because parent menu is in this module
        'cot_hierarchy'
    ],
    'data': [
        'wizard/chart_of_analytic_wizard_view.xml',
        'analytic_view.xml'
    ],
    'installable': True,
}
