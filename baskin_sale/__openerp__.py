# -*- coding: utf-8 -*-

{
    'name': 'Baskin Sales',
    'version': '1.0',
    'category': 'Sale',
    'description': '''''',
    'author': 'Onnet',
    'website': '',

    'depends': ['sale','web_readonly_bypass', 'sale_crm', 'base', 'br_multi_outlet','utm'],
    'data': [
        'views/sale_view.xml',
        'views/sale_area_region_config.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True
}
