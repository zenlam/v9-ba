# -*- coding: utf-8 -*-
{
    'name': 'Web Hide Duplicate',
    'version': '9.0.1.0.0',
    'author': 'Onnet Consulting Sdn Bhd',
    'website': 'https://on.net.my/',
    'category': 'Hidden',
    'summary': 'Allow to configuration for hide duplicate option in more menu',
    'description': """
Able to do configuration to hide duplicate option in more menu to specific models.
""",
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/web_hide_duplicate_view.xml'
    ],
    'installable': True,
    'application': False,
}
