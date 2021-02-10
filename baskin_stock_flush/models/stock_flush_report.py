# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class StockFlushDate(models.Model):
    """
    This will store the date and time of the flush operation. Also, used as a
    condition to generate stock related report.
    """
    _name = 'stock.flush.date'
    _description = 'Stock Flush Date'

    name = fields.Char('Name', required=True)
    flush_date = fields.Datetime('Flush Date', required=True)


class StockFlushReport(models.Model):
    """
    This will store the history of stock warehouse flushing in detail.
    """
    _name = 'stock.flush.report'
    _description = 'Stock Flush Report'

    name = fields.Char('Name', required=True)
    flush_date = fields.Datetime('Flush Date', required=True)
    warehouse_id = fields.Many2one('stock.warehouse',
                                   string='Warehouse',
                                   required=True)
    location_id = fields.Many2one('stock.location',
                                  string='Flush Location',
                                  required=True)
    flush_quant_ids = fields.One2many('stock.quant',
                                      'flush_id',
                                      string='Flush Quants')
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True,
                                 default=lambda self: self.env.user.company_id)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    flush_id = fields.Many2one('stock.flush.report', string='Flush')
