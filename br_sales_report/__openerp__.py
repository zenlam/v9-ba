# -*- coding: utf-8 -*-
{
    'name': "Baskin Robin Sales Report",
    'summary': """
            Baskin Robin Sales Report
        """,

    'description': """

    """,
    'author': 'Onnet Solution SDN BHD',
    'website': 'http://www.onnet.my',
    'version': '1.0',
    'depends': ['br_point_of_sale', 'report_xlsx'],
    'data': [
        'reports/br_sales_report_views.xml'
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
