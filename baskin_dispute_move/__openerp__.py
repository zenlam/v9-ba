# -*- coding: utf-8 -*-

{
    'name' : 'Baskin Dispute Stock Move',
    'version' : '1.0',
    'author':"Onnet Solution SDN BHD",
    'website':"http://www.onnet.my",
    'description': """
""",
    'depends' : ['stock',
                 'br_stock_request',
                 'baskin_grn_view',
                 'baskin_cake_ordering'],
    'data': [
            'views/dispute_move_view.xml'
            ],
    'qweb':[],
    'installable': True,
    'auto_install': False,
    'application':False,

}
