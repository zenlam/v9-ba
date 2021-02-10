{
    'name': "BR Track Order",
    'summary': """
        Track when user destroy order, click back after click payment 
    """,
    'description': """
        Track when user destroy order, click back after click payment
    """,
    'author': "Elephas",
    'website': "http://elephas.vn",
    'category': 'Point Of Sale',
    'version': '1.0',
    'depends': ['br_pos_refund'],
    'data': [
        'reports/views/pos_track_order_report.xml',
        'views/templates.xml',
        'security/ir.model.access.csv'
    ],
    'qweb': ['static/src/xml/track_order.xml'],
    'application': True,
    "installable": True,
    'auto_install': False,
}
