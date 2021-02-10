# -*- coding: utf-8 -*-

from openerp import fields, models


class FinancialItem(models.Model):
    _name = 'financial.item'

    name = fields.Char('Name', required=True)


class FinancialItemLine(models.Model):
    _name = 'financial.item.line'
    _rec_name = 'financial_item_id'

    financial_item_id = fields.Many2one(
                            'financial.item',
                            string='Name',
                            required=True)
    account_ids = fields.Many2many(
                    'account.account',
                    'account_financial_item_line_rel',
                    'financial_item_id',
                    'account_id',
                    string='Accounts')


class FinancialItemFormula(models.Model):
    _name = 'financial.item.formula'

    source_ratio_item_id = fields.Many2one('financial.item', string='Source Ratio')
    from_ratio_item_id = fields.Many2one('financial.item', string='From Ratio')
    to_ratio_item_id = fields.Many2one('financial.item', string='To Ratio')
