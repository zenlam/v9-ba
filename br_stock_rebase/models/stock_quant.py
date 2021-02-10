from openerp.osv import osv, fields
from openerp.exceptions import UserError
from openerp import tools
from openerp.tools.translate import _
from datetime import datetime, timedelta
import re
import time
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT



class BrStockQuant(osv.osv):
    _inherit = 'stock.quant'

    def _prepare_account_move_line(self, cr, uid, move, qty, cost, credit_account_id, debit_account_id, context=None):
        """
        Generate the account.move.line values to post to track the stock valuation difference due to the
        processing of the given quant.
        """
        if context is None:
            context = {}
        currency_obj = self.pool.get('res.currency')
        if context.get('force_valuation_amount'):
            valuation_amount = context.get('force_valuation_amount')
        else:
            if move.product_id.cost_method == 'average':
                valuation_amount = cost if move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal' else move.product_id.standard_price
            else:
                valuation_amount = cost if move.product_id.cost_method == 'real' else move.product_id.standard_price
        # the standard_price of the product may be in another decimal precision, or not compatible with the coinage of
        # the company currency... so we need to use round() before creating the accounting entries.
        valuation_amount = currency_obj.round(cr, uid, move.company_id.currency_id, valuation_amount * qty)
        # check that all data is correct
        if self.check_valuation_amount(cr, uid, move, valuation_amount, context=context):
            raise UserError(_("The found valuation amount for product %s is zero. Which means there is probably a configuration error. Check the costing method and the standard price") % (move.product_id.name,))
        partner_id = (move.picking_id.partner_id and self.pool.get('res.partner')._find_accounting_partner(move.picking_id.partner_id).id) or False
        debit_line_vals = {
            'name': move.name,
            'product_id': move.product_id.id,
            'quantity': qty,
            'product_uom_id': move.product_id.uom_id.id,
            'ref': move.picking_id and move.picking_id.name or False,
            'partner_id': partner_id,
            'debit': valuation_amount > 0 and valuation_amount or 0,
            'credit': valuation_amount < 0 and -valuation_amount or 0,
            'account_id': debit_account_id,
        }
        credit_line_vals = {
            'name': move.name,
            'product_id': move.product_id.id,
            'quantity': qty,
            'product_uom_id': move.product_id.uom_id.id,
            'ref': move.picking_id and move.picking_id.name or False,
            'partner_id': partner_id,
            'credit': valuation_amount > 0 and valuation_amount or 0,
            'debit': valuation_amount < 0 and -valuation_amount or 0,
            'account_id': credit_account_id,
        }
        return [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]

    def check_valuation_amount(self, cr, uid, move, valuation_amount, context=None):
        return move.company_id.currency_id.is_zero(valuation_amount)

    def get_quant_cost(self, cr, uid, quants, context={}):
        # group quants, ids by cost
        quant_cost_qty = {}
        quant_cost_ids = {}
        for quant in quants:
            if quant_cost_qty.get(quant.cost):
                quant_cost_qty[quant.cost] += quant.qty
                quant_cost_ids[quant.cost].append(quant.id)
            else:
                quant_cost_qty[quant.cost] = quant.qty
                quant_cost_ids[quant.cost] = [quant.id]
        return [quant_cost_qty, quant_cost_ids]

    def _create_account_move_line(self, cr, uid, quants, move, credit_account_id, debit_account_id, journal_id, context=None):
        quant_cost_qty, quant_cost_ids = self.get_quant_cost(cr, uid, quants, context=context)
        move_obj = self.pool.get('account.move')
        utc_context = context.copy()
        utc_context.update(tz='UTC')
        for cost, qty in quant_cost_qty.items():
            context.update(quant_ids=quant_cost_ids[cost])
            move_lines = self._prepare_account_move_line(cr, uid, move, qty, cost, credit_account_id, debit_account_id,context=context)
            start_date = time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

            picking = move.picking_id
            if picking and picking.origin:
                is_pos_session = self.pool.get('pos.session').search(cr, uid, [('name','=',picking.origin)])
                if is_pos_session:
                    start_date = move.date_expected or fields.date.context_today(self, cr, uid, context=utc_context)

            # Check if picking is created from order, if true then get start date from that order's session
            if picking:
                pos_order_id = self.pool.get('pos.order').search(cr, uid, [('picking_id', '=', picking.id)])
                if pos_order_id:
                    pos_order = self.pool.get('pos.order').browse(cr, uid, pos_order_id, context)
                    session = pos_order.session_id
                    # If session is rescue session then get its original session's start date
                    if session.rescue:
                        pattern = "RESCUE FOR (.+?)\)"
                        match = re.search(pattern, session.name)
                        if match:
                            # figure out why if don't reset session to None then can't assign new value to session
                            session = None
                            session_name = match.group(1)
                            session_id = self.pool.get('pos.session').search(cr, uid, [('name', '=', session_name)], context=context)
                            session = self.pool.get('pos.session').browse(cr, uid, session_id, context)
                    if session:
                        start_date = session.start_at
                        # date_done = session.start_at

            # Because start date is datetime when convert to journal entry date, only date is kept
            # and by default system store date without timestamp so for example: user sets
            # start_date = '01/02/2018 01:00:00' and timezone is GMT+8, in the database start_date
            # is '01/01/2018 17:00:00', when get date for accounting system get journal date
            # is '01/01/2018'
            timestamp = datetime.strptime(start_date, tools.DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(hours=8)
            # ts = fields.datetime.context_timestamp(cr, uid, timestamp, context)
            start_date = timestamp.strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            date = context.get('force_period_date', start_date)

            damage_remark = ''
            if move and move.remark_id:
                damage_remark = move.remark_id.name
            reverse_reason = ''
            if move.reason_of_reverse:
                reverse_reason = move.reason_of_reverse.name
                
            if credit_account_id == debit_account_id:
                if move_lines[0][2]['analytic_account_id'] != move_lines[1][2]['analytic_account_id']:
                    new_move = move_obj.create(cr, uid, {'journal_id': journal_id,
                                                         'line_ids': move_lines,
                                                         'date': date,
                                                         'ref': move.picking_id.name,
                                                         'memo':reverse_reason or damage_remark}, context=context)
                    move_obj.post(cr, uid, [new_move], context=context)
            else:
                new_move = move_obj.create(cr, uid, {'journal_id': journal_id,
                                                     'line_ids': move_lines,
                                                     'date': date,
                                                     'ref': move.picking_id.name,
                                                     'memo':reverse_reason or damage_remark}, context=context)
                move_obj.post(cr, uid, [new_move], context=context)
