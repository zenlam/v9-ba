# -*- coding: utf-8 -*-

{
    'name' : 'Baskin Fulfillment Report',
    'version' : '1.0',
    'author':"Onnet Solution SDN BHD",
    'website':"http://www.onnet.my",
    'description': """
""",
    'depends' : ['stock_inventory_adj', 'br_stock'],
    'data': [
        'data/fulfillment_report_show_by_data.xml',
        'wizard/fulfillment_report_view.xml',
        'security/ir.model.access.csv'
    ],
    'qweb':[],
    'installable': True,
    'auto_install': False,
    'application':False,

}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
