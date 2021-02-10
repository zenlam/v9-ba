# -*- coding: utf-8 -*-

{
    'name': 'List View Currency Issue',
    'version': '9.0.1.0.0',
    'author': 'Onnet Consulting Sdn Bhd',
    'category': 'Hidden',
    'description': """
List View Currency Issue
========================
Multiple currency symbol is not supported in list/tree view.
Actually it's already supported but due to wrong formation it creates issue.

    """,
    'website': 'https://on.net.my/',
    'depends': ['web'],
    'data': [
        'views/templates.xml',
    ],
    'installable': True,
    'auto_install': False,
}
