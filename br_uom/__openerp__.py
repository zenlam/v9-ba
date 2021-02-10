# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin UOM",

    'summary': """
        Customize uom: uom product, uom vendor
        """,

    'description': """
        link uom with product and vendor
    """,

    'author': "HanelSoft",
    'website': "http://hanelsoft.vn",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Product',
    'version': '1.0',

    # any module necessary for this one to work correctly

    'depends': [
        'stock_account',
        'purchase_requisition',
        'sale',
        'br_account_move_line_quant_stock_link',
        'product_expiry',
    ],


    # always loaded
    'data': [
        'views/br_uom_view.xml',
        'views/br_valuation_view.xml',
        'views/br_inventory_view.xml',
        'views/br_prod_lot_view.xml',
        'views/br_purchase_requisition_view.xml',
        'views/br_sale_order_view.xml',
        'views/br_account_invoice_view.xml',
        'views/br_stock_view.xml',
        'views/template.xml'
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
