from openerp import models, fields, api, _
from openerp.exceptions import UserError
from openerp.tools import float_round
from datetime import datetime
import psycopg2

class PosSession(models.Model):
    _inherit = 'pos.session'

    statement_ids_related = fields.One2many(comodel_name='account.bank.statement', compute='_get_statement_ids_related')
    picking_id = fields.Many2one(comodel_name='stock.picking', string='Picking')

    @api.model
    def _try_lock_session(self):
        for session in self:
            try:
                # Try to grab an exclusive lock on the session row from within the closing transaction
                session.env.cr.execute("""SELECT *
                                   FROM pos_session
                                   WHERE id = %s
                                   FOR UPDATE NOWAIT""",
                                (session.id,), log_exceptions=False)
            except psycopg2.OperationalError:
                session.env.cr.rollback()
                raise UserError(_("This session is currently being closed and may not be modified "))

    @api.multi
    def button_signout_confirm(self):
        self.ensure_one()
        self._try_lock_session()
        ir_model_data = self.env['ir.model.data']
        view_id = ir_model_data.get_object_reference('br_point_of_sale', 'pos_session_signout_confirm_form')[1]
        ctx = self.env.context.copy()
        ctx['session_ids'] = self.ids
        return {
            'name': _('Close Pos Session Confirmation'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'pos.session.signout.confirm',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def button_closing_confirm(self):
        self.ensure_one()
        self._try_lock_session()
        if self.cash_register_difference != 0:
            ir_model_data = self.env['ir.model.data']
            view_id = ir_model_data.get_object_reference('br_point_of_sale', 'pos_session_closing_confirm_form')[1]
            ctx = self.env.context.copy()
            ctx['session_ids'] = self.ids
            return {
                'name': _('Close Pos Session Confirmation'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'pos.session.closing.confirm',
                'views': [(view_id, 'form')],
                'view_id': view_id,
                'target': 'new',
                'context': ctx,
            }
        else:
            self.signal_workflow('close')

    @api.depends('statement_ids')
    @api.one
    def _get_statement_ids_related(self):
        # NOTE : comment line for filtering cash register line from payment's [request from Nicole to show it again]
        #self.statement_ids_related = self.statement_ids.filtered(lambda x: x.id != self.cash_register_id.id)
        self.statement_ids_related = self.statement_ids

    @api.multi
    def wkf_action_close(self):
        context = self.env.context.copy()
        context.update(skip_pos_order_statement=True)
        res = super(PosSession, self.with_context(context)).wkf_action_close()
        self.post_payment()
        self.create_picking()
        return res

    def _prepare_consolidated_orders(self):
        """

        :return: pos.order(...)
        """
        return self.order_ids.filtered(lambda x: not x.picking_id)

    def create_picking(self):
        """
        Consolidate all pickings from pos order then post them
        :return:
        """
        for session in self:
            move_qties = {}
            for order in session._prepare_consolidated_orders():
                for line in order.lines:
                    if line.product_id and line.product_id.type not in ['product', 'consu']:
                        continue
                    # Consolidate all orderlines base on product and uom
                    key = (line.product_id.id, line.product_id.uom_id.id)
                    if key not in move_qties:
                        move_qties[key] = line.qty
                    else:
                        move_qties[key] += line.qty
            if move_qties:
                picking_vals = session.prepare_picking_vals(move_qties)
                picking = self.env['stock.picking'].create(picking_vals)
                if picking:
                    picking.action_confirm()
                    picking.force_assign()
                    # Mark pack operations as done
                    picking.action_assign()
                    for pack in picking.pack_operation_ids:
                        pack.write({'qty_done': pack.product_qty})
                        if pack.product_id.tracking == 'lot':
                            total_lot_qty = 0
                            for lot in pack.pack_lot_ids:
                                pack.write({'qty': lot.qty_todo})
                                total_lot_qty += lot.qty_todo
                            remaining_qty = float_round(pack.product_qty - total_lot_qty, precision_rounding=pack.product_uom_id.rounding)
                            if remaining_qty:
                                # In case there there is no stock left then negative quant is created, it should be place under negative lot
                                session.generate_lot_negative(pack.product_id, pack.id, remaining_qty)
                    picking.action_done()
                    session.write({'picking_id': picking.id})

    def prepare_picking_vals(self, move_qties):
        """
        :param move_qties: qty of grouped moves
        :return:
        """
        moves = []
        config = self.config_id
        picking_type = config.picking_type_id
        location = config.stock_location_id
        outlet = self.outlet_id
        analytic_account_id = outlet and outlet.analytic_account_id and outlet.analytic_account_id.id or False
        # Get destination location from outlet
        if (not picking_type) or (not picking_type.default_location_dest_id):
            customerloc, supplierloc = self.env['stock.warehouse']._get_partner_locations()
            destination_id = customerloc.id
        else:
            destination_id = picking_type.default_location_dest_id.id
        for key in move_qties:
            moves.append(
                (0, 0, {
                    'name': self.name,
                    'product_uom': key[1],
                    'picking_type_id': picking_type.id,
                    'product_id': key[0],
                    'product_uom_qty': move_qties[key],
                    'state': 'draft',
                    'location_id': location.id,
                    'location_dest_id': destination_id,
                    'date_expected': self.start_at,
                    'account_analytic_id': analytic_account_id
                })
            )

        return {
            'analytic_account_id': analytic_account_id,
            'move_lines': moves,
            'origin': self.name,
            'date_done': self.start_at,
            'min_date': self.start_at,
            'picking_type_id': picking_type.id,
            'company_id': config.company_id.id,
            'move_type': 'direct',
            'location_id': location.id,
            'location_dest_id': destination_id,
        }

    def generate_lot_negative(self, product, ops_id, qty):
        """
        Generate negative lot for product
        :param product:
        :param ops_id:
        :param qty:
        :return:
        """
        lot_name = 'Negative Quantity'
        new_lot_id = self.env['stock.production.lot'].search([('name', '=', lot_name), ('product_id', '=', product.id)], limit=1)
        if not new_lot_id:
            supplier = False
            supplier_info_id = self.env['product.supplierinfo'].search([('product_tmpl_id', '=', product.product_tmpl_id.id)], limit=1)
            if supplier_info_id:
                supplier = supplier_info_id.name
            lot_vals = {
                'product_id': product.id,
                'name': lot_name,
                'br_supplier_id': supplier and supplier.id or False,
                'removal_date': datetime.now()
            }
            new_lot_id = self.env['stock.production.lot'].create(lot_vals)

        vals = {
            'lot_id': new_lot_id.id or False,
            'operation_id': ops_id,
            'qty': qty
        }
        ls_op_lot_tmp = self.env['stock.pack.operation.lot'].search(([('lot_id', '=', new_lot_id.id), ('operation_id', '=', ops_id)]))
        if not ls_op_lot_tmp:
            self.env['stock.pack.operation.lot'].create(vals)
        else:
            new_qty = ls_op_lot_tmp.qty + qty
            ls_op_lot_tmp.write({'qty': new_qty})

    def post_payment(self):
        """
        Consolidate all payment which are created from pos.order then post them
        :return:
        """
        account_bank_statement_line = self.env['account.bank.statement.line']
        for s in self:
            for statement in s.statement_ids:
                to_counterpart = {}
                for st_line in statement.line_ids.filtered(lambda x: x.pos_statement_id):
                    if st_line.statement_id.journal_id.type not in ['bank', 'cash']:
                        raise UserError(_("The type of the journal for your payment method should be bank or cash "))
                    # Group key
                    key = (statement.journal_id.id, st_line.account_id.id, st_line.currency_id.id or False)
                    if key in to_counterpart:
                        to_counterpart[key]['amount'] += st_line.amount
                        to_counterpart[key]['amount_currency'] += st_line.amount_currency
                    else:
                        to_counterpart[key] = {
                            'statement_id': statement.id,
                            'currency_id': st_line.currency_id.id or False,
                            'amount': st_line.amount,
                            'amount_currency': st_line.amount_currency,
                            'account_id': st_line.account_id.id,
                            'date': s.start_at,
                            'name': statement.name,
                            'ref': s.name,
                        }
                for k, vals in to_counterpart.items():
                    new_context = self.env.context.copy()
                    new_context.update(move_name=vals['name'])
                    # Fake new statement line with consolidated data
                    temp_st_line = account_bank_statement_line.with_context(new_context).new(values=vals)
                    temp_st_line.fast_counterpart_creation()
