# -*- coding: utf-8 -*-

{
    'name': 'Baskin PO Receivable Listing',
    'version': '1.0',
    'category': 'Purchase',
    'description': '''''',
    'author': 'Onnet',
    'website': '',
    'depends': ['purchase','web_readonly_bypass'],
    'data': [
        'views/purchase_view.xml',
        'views/purchase_line_cons_stock_review_listing.xml',
        'views/purchase_line_service_review_listing.xml'
    ],
    'installable': True
}
