# -*- coding: utf-8 -*-
{
    'name': 'Fields Options Config',
    'version': '9.0.1.0.0',
    'author': 'Onnet Consulting Sdn Bhd',
    'website': 'https://on.net.my/',
    'category': 'Hidden',
    'summary': 'Easily manage field options attributes',
    'description': """
Field Options Attribute Configuration
=====================================
User can easily manage options attribute of any field.

Add options attribute in any field without inherit existing view.

Supported Field Types
----------------------
* Many2one (M2O)
* Many2many (M2M)

Supported Options Attributes
----------------------------
* no_open
* no_create
* no_create_edit

""",
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/ir_model_fields_options_view.xml',
    ],
    'installable': True,
    'application': False,
}
