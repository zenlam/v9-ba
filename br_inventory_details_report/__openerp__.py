# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbins Inventory Detail Report",

    'summary': """
        Baskin Robbins Inventory Detail Report
        """,

    'description': """
       Inventory detail report shows incoming / outgoing of stock
    """,

    'author': "LongDT",
    'website': "",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Warehouse',
    'version': '1.0',

    # any module necessary for this one to work correctly

    'depends': ['report_xlsx', 'br_multi_outlet', 'baskin_stock_flush'],


    # always loaded
    'data': [
        'views/inventory_details.xml'
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
