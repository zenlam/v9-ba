{
    'name': 'Baskin Robbin Mall Integration Report',
    'version': '1.0',
    'category': 'Baskin Robbin',
    'author': 'Elephas',
    'depends': ['point_of_sale', 'br_multi_outlet', 'br_api_caller', 'report_txt'],
    'data': [
        'security/ir.model.access.csv',
        'views/report_paperformat.xml',
        'views/mall_integration_config.xml',
        'views/pos_order_summary_report.xml',
        'views/gto_log.xml',
        'views/request_config.xml',
        'views/gto_log_report.xml',
        'wizard/br_run_request_config.xml',
        'data/request_config.xml',
         ],
    'installable': True,
    'auto_install': False,
}
