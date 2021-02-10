from openerp import api, models, fields, _
from openerp.fields import Datetime as fieldsDatetime


class WizardValuationHistory(models.TransientModel):
    _inherit = 'wizard.valuation.history'

    @api.multi
    def open_table(self):
        self.ensure_one()
        ctx = dict(
            self._context,
            history_date=self.date,
            search_default_group_by_product=True,
            search_default_group_by_location=True)

        action = self.env['ir.model.data'].xmlid_to_object('stock_account.action_stock_history')
        if not action:
            action = {
                'view_type': 'form',
                'view_mode': 'tree,graph,pivot',
                'res_model': 'stock.history',
                'type': 'ir.actions.act_window',
            }
        else:
            action = action[0].read()[0]

        action['domain'] = "[('date', '<=', '" + self.date + "')]"
        action['name'] = _('Stock Value At Date')
        action['context'] = ctx
        return action

class StockHistory(models.Model):
    _inherit = 'stock.history'

    # Bug fixed for odoo9
    # https://github.com/odoo/odoo/commit/51d072db444bfd2dcad18122b502a4d3a98627f4
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super(StockHistory, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        if 'inventory_value' in fields:
            date = self._context.get('history_date', fieldsDatetime.now())
            stock_history = self.env['stock.history']
            group_lines = {}
            for line in res:
                domain = line.get('__domain', domain)
                group_lines.setdefault(str(domain), self.search(domain))
                stock_history |= group_lines[str(domain)]

            histories_dict = {}
            not_real_cost_method_products = stock_history.mapped('product_id').filtered(lambda product: product.cost_method != 'real')
            if not_real_cost_method_products:
                self._cr.execute("""SELECT DISTINCT ON (product_id, company_id) product_id, company_id, cost
                        FROM product_price_history
                        WHERE product_id in %s AND datetime <= %s
                        ORDER BY product_id, company_id, datetime DESC, id DESC""", (tuple(not_real_cost_method_products.ids), date))
                for history in self._cr.dictfetchall():
                    histories_dict[(history['product_id'], history['company_id'])] = history['cost']

            for line in res:
                inv_value = 0.0
                for stock_history in group_lines.get(str(line.get('__domain', domain))):
                    product = stock_history.product_id
                    if product.cost_method == 'real':
                        price = stock_history.price_unit_on_quant
                    else:
                        price = histories_dict.get((product.id, stock_history.company_id.id), 0.0)
                    inv_value += price * stock_history.quantity
                line['inventory_value'] = inv_value

        return res