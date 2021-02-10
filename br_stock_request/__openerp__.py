# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Stock Request",
    'summary': """
            Baskin Robbin Stock Request
        """,

    'description': """
        Baskin Robbin Stock Request
    """,
    'author': "Elephas",
    'website': "http://Elephas.vn",
    'category': 'Stock',
    'version': '0.1',
    'depends': ['br_pos_stock', 'baskin_dispute_picking', 'baskin_cronjob_user'],
    'data': [
        'views/stock_request_form.xml',
        'views/stock_request_transfer.xml',
        'views/stock_warehouse.xml',
        'views/stock.xml',
        'views/outlet.xml',
        'views/br_stock_request_transfer_log.xml',
        'wizard/stock_mass_edit.xml',
        'wizard/stock_mass_transfer.xml',
        'wizard/stock_transfer_dispute.xml',
        'wizard/transfer_cancel_confirmation.xml',
        'data/ir_model.xml',
        'data/ir_sequence.xml',
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
