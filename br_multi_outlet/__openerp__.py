# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Outlets",

    'summary': """
        Create multiple outlets for a company in Openerp
        """,

    'description': """
        Allow creating multiple outlets for a company
        A user can be authorized to access more than 1 outlet
        Other entities ( pos_order, purchase_order ... ) are tagged with equivalent outlet_id as well
    """,

    'author': "Hanelsoft/TruongNN",
    'website': "http://hanelsoft.vn",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Warehouse',
    'version': '1.0',

    # any module necessary for this one to work correctly

    'depends': ['base', 'point_of_sale', 'account', 'sale', 'stock'],


    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/outlet_view.xml',
        'views/point_of_sale_view.xml',
        'views/outlet_tag.xml',
        'reports/pos_details_report.xml',
        'security/ir_rule_view.xml'
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
