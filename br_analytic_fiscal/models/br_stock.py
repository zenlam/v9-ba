from openerp import models, fields, api, SUPERUSER_ID, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import timedelta
from datetime import datetime
import time
import logging

_logger = logging.getLogger(__name__)

class br_ProcurementOrder(models.Model):
    _inherit = 'procurement.order'
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')], track_visibility='always')

    @api.model
    def _run_move_create(self, procurement):
        vals = super(br_ProcurementOrder, self)._run_move_create(procurement)
        if procurement.account_analytic_id:
            vals.update({'account_analytic_id': procurement.account_analytic_id.id})
        elif procurement.location_id:
            vals.update({'account_analytic_id': procurement.rule_id.location_src_id.br_analytic_account_id.id if procurement.rule_id.location_src_id.br_analytic_account_id else False})
        return vals


class br_stock_quant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _prepare_account_move_line(self, move, qty, cost, credit_account_id, debit_account_id):
        """
        Get analytic account for debit & credit accounts
        """
        res = super(br_stock_quant, self)._prepare_account_move_line(move, qty, cost, credit_account_id, debit_account_id)
        # Remove this check later
        if not self.env.context.get('analytic_account_id', False):
            move_analytic_account = move.account_analytic_id.id or False
            credit_analytic_account_id = self.env.context.get('credit_analytic_account', False) or move_analytic_account
            if self.env.context.get('debit_analytic_account', False):
                debit_analytic_account_id = self.env.context.get('debit_analytic_account')
            elif move_analytic_account:
                debit_analytic_account_id = move_analytic_account
            else:
                des_location = move.location_dest_id
                debit_analytic_account_id = des_location.get_analytic_account() or False
            # Debit account
            if res and res[0] and res[0][2]:
                res[0][2].update({'analytic_account_id': debit_analytic_account_id})

            # Credit account
            if res and res[1] and res[1][2]:
                res[1][2].update({'analytic_account_id': credit_analytic_account_id})
        return res

    def _account_entry_move(self, cr, uid, quants, move, context=None):
        """
        Accounting Valuation Entries

        quants: browse record list of Quants to create accounting valuation entries for. Unempty and all quants are supposed to have the same location id (thay already moved in)
        move: Move to use. browse record
        """
        if context is None:
            context = {}
        location_obj = self.pool.get('stock.location')
        location_from = move.location_id
        location_to = quants[0].location_id
        company_from = location_obj._location_owner(cr, uid, location_from, context=context)
        company_to = location_obj._location_owner(cr, uid, location_to, context=context)

        if move.product_id.valuation != 'real_time' or move.product_id.type != 'product':
            return False
        for q in quants:
            if q.owner_id:
                # if the quant isn't owned by the company, we don't make any valuation entry
                return False
            if q.qty <= 0:
                # we don't make any stock valuation for negative quants because the valuation is already made for the counterpart.
                # At that time the valuation will be made at the product cost price and afterward there will be new accounting entries
                # to make the adjustments when we know the real cost price.
                return False

        # in case of routes making the link between several warehouse of the same company, the transit location belongs to this company, so we don't need to create accounting entries
        # Create Journal Entry for products arriving in the company
        ctx = context.copy()
        if not move.origin_returned_move_id:
            ctx['credit_analytic_account'] = move.location_id.get_analytic_account()
        if move.origin_returned_move_id:
            ctx['debit_analytic_account'] = move.location_dest_id.get_analytic_account()

        if company_to and (
                        move.location_id.usage not in ('internal', 'transit') and move.location_dest_id.usage == 'internal'):
            ctx['force_company'] = company_to.id
            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move,
                                                                                                   context=ctx)
            if location_from and location_from.usage == 'customer':
                # goods returned from customer
                self._create_account_move_line(cr, uid, quants, move, acc_dest, acc_valuation, journal_id, context=ctx)
            else:
                self._create_account_move_line(cr, uid, quants, move, acc_src, acc_valuation, journal_id, context=ctx)

        # Create Journal Entry for products leaving the company

        if company_from and (
                        move.location_id.usage == 'internal' and move.location_dest_id.usage not in ('internal', 'transit')):
            ctx['force_company'] = company_from.id

            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move,
                                                                                                   context=ctx)
            if location_to and location_to.usage == 'supplier':
                # goods returned to supplier
                self._create_account_move_line(cr, uid, quants, move, acc_valuation, acc_src, journal_id, context=ctx)
            else:
                self._create_account_move_line(cr, uid, quants, move, acc_valuation, acc_dest, journal_id, context=ctx)

        # transfer internal
        # Create Journal Entry for case internal transfer
        if move.location_id.company_id \
                and move.location_dest_id.company_id \
                and move.location_dest_id.company_id == move.location_id.company_id \
                and move.location_id.usage in ('internal', 'transit') \
                and move.location_dest_id.usage in ('internal', 'transit'):
            ctx['force_company'] = move.location_dest_id.company_id.id
            # self.env.context = ctx
            # create jounal
            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=ctx)
            self._create_account_move_line_internal(cr, uid, quants, move, acc_dest, acc_valuation, journal_id,
                                                    context=ctx)

    @api.model
    def _create_account_move_line_internal(self, quants, move, credit_account_id, debit_account_id, journal_id):
        # group quants by cost
        quant_cost_qty = {}
        quant_cost_ids = {}
        for quant in quants:
            if quant_cost_qty.get(quant.cost):
                quant_cost_qty[quant.cost] += quant.qty
                quant_cost_ids[quant.cost].append(quant.id)
            else:
                quant_cost_qty[quant.cost] = quant.qty
                quant_cost_ids[quant.cost] = [quant.id]

        move_obj = self.env['account.move']
        # date_expected = move.date_expected or fields.Date.context_today(self)
        # date_expected = datetime.strptime(date_expected, DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(hours=8)
        # date_expected = date_expected.date().strftime(DEFAULT_SERVER_DATE_FORMAT)
        # date = self.env.context.get('force_period_date', date_expected)

        # NOTE : BASKIN-591: All the stock journal entry should be post based on date when stock picking and stock move done
        date_done = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        date_done = datetime.strptime(date_done, DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(hours=8)
        date_done = date_done.date().strftime(DEFAULT_SERVER_DATE_FORMAT)
        date = self.env.context.get('force_period_date', date_done)
        
        iindex = 0
        for cost, qty in quant_cost_qty.items():
            my_context = self.env.context.copy()
            my_context.update(quant_ids=quant_cost_ids[cost])
            # get data moveline from des location internal
            move_lines = self.with_context(my_context)._prepare_account_move_line(move, qty, cost, debit_account_id, debit_account_id)
            debit, credit = move_lines

            # get data moveline from src location internal
            if move_lines and move_lines[0] and move_lines[0][2] and 'analytic_account_id' in move_lines[0][2] and move_lines[0][2]['analytic_account_id']:
                quant = quants[iindex]
                ls_move_of_quant = quant.history_ids
                reference = move.picking_id.name or ''
                aml = False
                for move_item in ls_move_of_quant.sorted(key=lambda r: -r.id):
                    if not quant.reservation_id and move.picking_id.location_id.id == move_item.location_dest_id.id:
                        aml = self.with_context(my_context)._prepare_account_move_line(move_item, qty, cost, debit_account_id, debit_account_id)
                        break
                if aml:
                    _, credit = aml
                else:
                    credit[2]['analytic_account_id'] = move.picking_id.location_id.get_analytic_account()
                move_lines = [debit, credit]
                if debit[2]['analytic_account_id'] != credit[2]['analytic_account_id']:
                    product_pool = self.env['product.product']
                    for l in move_lines:
                        product = product_pool.browse(l[2]['product_id'])
                        l[2].update(
                            name=product.name_template if not product.default_code else '[%s] %s' % (product.default_code, product.name_template)
                        )
                    new_move = move_obj.create({'journal_id': journal_id,
                                                'line_ids': move_lines,
                                                'date': date,
                                                'ref': reference})
                    new_move.post()
                    new_move.write({'ref': reference})
                else:
                    #TODO : check this is the correct to ignor the posting if not then need to fix.
                    _logger.info("""Here if analytic account is same for credit and debit then it will just ignore the accounting entry which is wrong. by right we should stop the transaction""")



            iindex += 1
