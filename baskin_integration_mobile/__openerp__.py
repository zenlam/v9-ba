# -*- coding: utf-8 -*-
{
    'name': 'Baskin Robbin Integration: Mobile',
    'version': '1.0',
    'author': 'Onnet Consulting SDN BHD',
    'website': 'http://www.onnet.my',
    'description': '''
    This module helps to integrate Baskin Robbin System with the mobile apps.
    ''',
    'depends': [
        'restful', 'baskin_integration_base'
    ],
    'data': [
        'data/ir_cron_data.xml',
        'data/res_users_data.xml',
        'data/third_party_data.xml',
        'security/ir.model.access.csv',
        'views/br_bundle_promotion_views.xml',
        'views/br_multi_outlet_outlet_views.xml',
        'views/outlet_mobile_app_status_views.xml',
        'views/third_party_views.xml',
        'views/br_config_voucher_views.xml',
        'views/templates.xml'
    ],
    'qweb': [
        'static/src/xml/pos.xml',
    ],
    'installable': True,
}
