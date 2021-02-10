# -*- coding: utf-8 -*-

{
    'name' : 'Baskin Stock Flush',
    'version' : '1.0',
    'author':"Onnet Consulting SDN BHD",
    'website':"http://www.onnet.my",
    'description': """
    Allow user to create flush location, move the quant to flush location
""",
    'depends' : ['br_stock'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/stock_flush_report_views.xml',
        'views/stock_warehouse_views.xml',
        'wizard/stock_flush_views.xml',
    ],
    'qweb':[],
    'installable': True,
    'auto_install': False,
    'application':False,

}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
