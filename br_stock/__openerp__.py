# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Stock Module",

    'summary': """
    Customize default stock module
        """,
    'description': """
    Customize default stock module
    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Warehouse',
    'version': '1.0',
    'depends': ['br_analytic_fiscal', 'br_stock_rebase', 'br_product', 'baskin_dispute_picking','br_base','stock'],
    'data': [
        'reports/report_stock_picking.xml',
        'reports/stock_transfer_note.xml',
        'views/stock_location.xml',
        'views/stock_inventory.xml',
        'views/stock_picking_type.xml',
        'views/stock.xml',
        'views/stock_history_views.xml',
        'views/br_stock_view.xml',
        'views/br_location_view.xml',
        'views/vehicle.xml',
        'views/partner.xml',
        'security/stock_security.xml'
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
