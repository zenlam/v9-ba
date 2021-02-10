# -*- coding: utf-8 -*-
{
    'name': "Account Move Line - Stock Quant Link",
    'summary': """
        Create link between account move line and stock
    """,
    'description': """
        Add new fields:
        - Account move line: move_id (Many2one, rel: stock.move), quant_ids (Many2many, rel: stock.quant)
        - Stock move: inventory_line_id(Many2one, rel: stock.inventory.line)
    """,
    'author': "LongDT",
    'website': "",
    'category': 'Warehouse',
    'version': '1.0',
    'depends': ['account','br_stock_rebase'],
    'data': [
        'account_view.xml',
        'wizard/journal_item_po_wizard_view.xml',

    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
    "application": True,
}
