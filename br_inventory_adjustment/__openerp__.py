# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Inventory Adjustment",
    'summary': """
            Baskin Robbin Inventory Adjustment
        """,

    'description': """
        Baskin Robbin Inventory Adjustment
    """,
    'author': "Elephas",
    'website': "http://Elephas.vn",
    'category': 'stock',
    'version': '0.1',
    'depends': ['br_stock_expiry', 'br_consumable_stock_flag'],
    'data': [
        'wizard/stock_inventory_adjustment_review.xml',
        'wizard/stock_inventory_set_action.xml',
        'views/stock_inventory.xml',
        'views/stock_inventory_template.xml',
        'views/stock_inventory_schedule.xml',
        'data/ir_cron.xml',
        'data/ir_data.xml',
        'security/security.xml',
    ],
    'demo': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
