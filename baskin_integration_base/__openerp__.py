# -*- coding: utf-8 -*-
{
    'name': 'Baskin Robbin Integration: Base',
    'version': '1.0',
    'author': 'Onnet Consulting SDN BHD',
    'website': 'http://www.onnet.my',
    'description': '''
    This module helps to integrate Baskin Robbin System with the third party.
    ''',
    'depends': [
        'br_pos_refund'
    ],
    'data': [
        'data/third_party_data.xml',
        'data/res_groups.xml',
        'data/ir_cron_data.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        'reports/report_receipt.xml',
        'views/br_bundle_promotion_views.xml',
        'views/br_config_voucher_views.xml',
        'views/br_multi_outlet_outlet_views.xml',
        'views/outlet_facility_views.xml',
        'views/pos_order_views.xml',
        'views/product_product_views.xml',
        'views/third_party_views.xml',
        'views/res_company.xml',
        'views/templates.xml',
        'wizard/full_data_sync_views.xml'
    ],
    'qweb': [
        'static/src/xml/pos.xml',
        'static/src/xml/report_receipt.xml'
    ],
    'installable': True,
}
