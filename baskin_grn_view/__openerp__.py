# -*- coding: utf-8 -*-

{
    'name' : 'Baskin GRN View',
    'version' : '1.0',
    'author':"Onnet Solution SDN BHD",
    'website':"http://www.onnet.my",
    'description': """
""",
    'depends' : ['stock',
                 'br_stock_request',
                 'br_consumable_stock_flag',
                 'baskin_dispute_picking'],
    'data': [
            'security/security.xml',
            'views/menu.xml',
            'views/warehouse_grn_view.xml',
            'views/stock_view.xml',
            'views/warehouse_processing_view.xml',
            'views/production_stock_views.xml',
            'views/pending_damaged_view.xml',
            'views/pending_internal_transfer_view.xml',
            'views/pending_trade_sales_view.xml'
            ],
    'qweb':[],
    'installable': True,
    'auto_install': False,
    'application':False,

}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
