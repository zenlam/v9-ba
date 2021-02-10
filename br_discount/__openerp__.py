# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin POS Discount",
    'summary': """
        Discount on POS sale order """,

    'description': """
        Discount based on
        - Total
        - Order line
        - Staff
        - Bundle Promotion
        - Sampling and Damaged & Wasted
    """,

    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Point of Sale',
    'version': '0.1',
    'depends': ['pos_discount','br_point_of_sale'],
    'data': [
        'data/sequence_data.xml',
        'data/ir_cron.xml',
        'data/default_barcode_patterns.xml',
        'views/views.xml',
        'views/br_pos.xml', # loading *.js, *.css
        'views/view_user.xml', # loading *.js, *.css
        'views/template.xml',
        'views/voucher_excel.xml',
        'views/voucher_listing.xml',
        'reports/x_report.xml',
        'wizard/br_promotion_voucher_gen_view.xml',
        'security/ir.model.access.csv',
    ],
    'qweb': ['static/src/xml/discount.xml'],
    # 'css': [
    #     'static/src/css/discount.css',
    # ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
