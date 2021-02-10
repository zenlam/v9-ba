# -*- coding: utf-8 -*-
{
    "name": "Baskin Asset Analytic Account",
    "version": "1.0",
    "category": "Tools",
    "description": """
    - Provide a way to transfer asset to other accounts (outlets).
    - Add analytic account at depreciation line level
    """,
    "author": "Onnet Solutions",
    "depends": ["account_asset"],
    'website': "",
    "data": [
        'security/ir.model.access.csv',
        'account_asset_view.xml',
        'wizards/update_asset_account_view.xml',
        'wizards/br_account_asset_log_view.xml',
    ],
    "installable": True,
    "auto_install": False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
