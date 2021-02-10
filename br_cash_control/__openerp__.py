# -*- coding: utf-8 -*-
{
    'name': "Baskin Robbin Cash Control",
    'summary': """
            Baskin Robbin Cash Control
        """,

    'description': """

    """,
    'author': "Hanelsoft",
    'website': "http://hanelsoft.vn",
    'category': 'Point Of Sale',
    'version': '0.1',
    'depends': ['br_account', 'report_xlsx', 'br_multi_outlet'],
    'data': [
        # 'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/cash_control.xml',
        'views/box_account.xml',
        'views/multi_outlet.xml',
        'views/pos_session.xml',
        'reports/outlet_cash_control_report.xml',
    ],
    'demo': [
    ],
    'application': True,
    "installable": True,
    'auto_install': False,
}
