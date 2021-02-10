from openerp import api, models, fields, tools


class StockMove(models.Model):
    _inherit = 'stock.move'

    # this field will be used to map the pos order line with the stock move.
    # Mapping using character field is risky, but add a m2o field in stock move
    # table will affects the performance too due to stock move is a massive
    # table
    pos_order_line_ref = fields.Char(string='Pos Order Line Reference')
