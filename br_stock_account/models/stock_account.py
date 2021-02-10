from openerp import models, api, SUPERUSER_ID, fields


class BRStockQuant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _prepare_account_move_line(self, move, qty, cost, credit_account_id, debit_account_id):
        """
        Set account when do inventory ajustment
        :param move:
        :param qty:
        :param cost:
        :param credit_account_id:
        :param debit_account_id:
        :return:
        """
        if move.inventory_id:
            journal_id, acc_src, acc_destination, acc_valuation = self._get_accounting_data_for_valuation(move)
            category = move.product_id.categ_id
            if category:
                categ_loss_acc = category.property_stock_account_loss_categ_id
                categ_excess_acc = category.property_stock_account_excess_categ_id
                if credit_account_id == acc_valuation:
                    if categ_loss_acc:
                        debit_account_id = categ_loss_acc.id
                elif credit_account_id in [acc_src, acc_destination]:
                    if categ_excess_acc:
                        credit_account_id = categ_excess_acc.id
        res = super(BRStockQuant, self)._prepare_account_move_line(move, qty, cost, credit_account_id, debit_account_id)
        return res


class StockMove(models.Model):
    _inherit = 'stock.move'

    def action_done(self, cr, uid, ids, context=None):
        self.product_price_update_before_done(cr, uid, ids, context=context)
        res = super(StockMove, self).action_done(cr, uid, ids, context=context)
        #self.product_price_update_after_done(cr, uid, ids, context=context)
        return res

    def product_price_update_before_done(self, cr, uid, ids, context=None):
        product_obj = self.pool.get('product.product')
        tmpl_dict = {}
        for move in self.browse(cr, uid, ids, context=context):
            # adapt standard price on incomming moves if the product cost_method is 'average'
            if move.location_id.usage == 'supplier':
                product = move.product_id
                product_id = move.product_id.id
                qty_available = move.product_id.qty_available
                if tmpl_dict.get(product_id):
                    product_avail = qty_available + tmpl_dict[product_id]
                else:
                    tmpl_dict[product_id] = 0
                    product_avail = qty_available
                # if the incoming move is for a purchase order with foreign currency, need to call this to get the same value that the quant will use.
                price_unit = self.pool.get('stock.move').get_price_unit(cr, uid, move, context=context)
                if product_avail <= 0:
                    new_std_price = price_unit
                else:
                    # Get the standard price
                    amount_unit = product.standard_price
                    new_std_price = ((amount_unit * product_avail) + (price_unit * move.product_qty)) / (product_avail + move.product_qty)
                tmpl_dict[product_id] += move.product_qty
                # Write the standard price, as SUPERUSER_ID because a warehouse manager may not have the right to write on products
                ctx = dict(context or {}, force_company=move.company_id.id)
                product_obj.write(cr, SUPERUSER_ID, [product.id], {'standard_price': new_std_price}, context=ctx)