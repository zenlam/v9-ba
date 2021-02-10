#!/usr/bin/python
# -*- encoding: utf-8 -*-

{
    'name': "Notify Onsave",

    'summary': """
        Show notify when click save on popup
    """,
    'description': """
        Add context to action with following format: "{notify: {'title': <Title>, 'message': <message>}}"
    """,
    'author': "Elephas",
    'category': 'Web',
    'version': '1.0',
    'depends': ['web'],
    'data': [
        'views/view.xml'
    ],
    'qweb': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,

}
