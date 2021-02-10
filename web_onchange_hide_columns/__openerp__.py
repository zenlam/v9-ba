# -*- coding: utf-8 -*-

{
    'name': 'Conditional Hide x2Many Tree View Columns',
    'description': """
    Odoo doesn't allow to set condition to hide column in x2many tree view because
    normally conditional display is mean to be used on record data so it makes sense that
    a column in tree view can't be hided based on its row's data but that shouldn't stop us
    from hiding columns based on parent value. This module allow you to hide column
    on x2many tree view using parent view values.
    Usage: create a related field to origin field to bypass view validation (need improve, anyone ?)
    then add 'invisible' to 'attrs' attribute, it should be something like this:
    <field name="foo" attrs="{'invisible': [('field_related', <condition>, <value>)]}/>"
    """,
    'version': '9.0.1.1.0',
    'author': 'Longdt',
    'depends': [
        'web',
    ],
    'demo': [],
    'website': '',
    'data': [
        'views/web_onchange_hide_columns.xml',
    ],
    'installable': True,
    'auto_install': False,
}
