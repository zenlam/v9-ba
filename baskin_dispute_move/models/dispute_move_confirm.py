from openerp.exceptions import ValidationError, UserError
from openerp import tools
from openerp import models, fields, api
from openerp.tools.translate import _


class DisputeStockMoveReport(models.Model):
    _inherit = 'stock.move.report'

    request_line_id = fields.Many2one(comodel_name='br.stock.request.transfer.line', string="Transfer Line")
    request_id = fields.Many2one(comodel_name='br.stock.request.transfer', string="Request Transfer")
    request_expected_date = fields.Datetime(related='request_id.expected_date')
    request_date_order = fields.Datetime(related='request_id.date_order')
    request_delivered_qty = fields.Float(related='request_line_id.delivered_qty')
    request_dispute_qty = fields.Float(related='request_line_id.dispute_qty')
    is_dispute_move = fields.Boolean(string="Dispute Move")
    is_accept_dispute = fields.Boolean(string='Accept Dispute')
    is_reject_dispute = fields.Boolean(string='Reject Dispute')
    is_disagree_dispute = fields.Boolean(string='Disagree Dispute')
    adjusted_dispute_qty = fields.Float(string='Adjusted Dispute Qty')
    initial_move_qty = fields.Float(string="Initial Move Qty")

    @api.constrains('is_disagree_dispute', 'adjusted_dispute_qty')
    def check_adjusted_qty_zero(self):
        if self.is_disagree_dispute and self.adjusted_dispute_qty <= 0:
            raise ValidationError(_('Adjusted Move Quantity should not less than or equal to zero.'))

    @api.onchange('is_accept_dispute')
    def _onchange_is_accept_dispute(self):
        if self.is_accept_dispute:
            self.is_reject_dispute = False
            self.is_disagree_dispute = False
            self.adjusted_dispute_qty = 0

    @api.onchange('is_reject_dispute')
    def _onchange_is_reject_dispute(self):
        if self.is_reject_dispute:
            self.is_accept_dispute = False
            self.is_disagree_dispute = False
            self.adjusted_dispute_qty = 0

    @api.onchange('is_disagree_dispute')
    def _onchange_is_disagree_dispute(self):
        if self.is_disagree_dispute:
            self.is_accept_dispute = False
            self.is_reject_dispute = False
        self.adjusted_dispute_qty = 0

    @api.multi
    def check_dispute_action(self):
        """
        Raise an error if the user does not choose an action for the selected moves.
        :return:
        """
        for move in self:
            dispute_action = False
            if move.is_accept_dispute ^ move.is_reject_dispute ^ (
                    move.is_disagree_dispute and move.adjusted_dispute_qty != 0):
                dispute_action = True
            if not dispute_action:
                raise UserError(_('Please select an action for every dispute move.'))

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'stock_move_report')
        cr.execute("""
            CREATE or REPLACE VIEW stock_move_report as (

                select

                    id,
                    origin,
                    create_date,
                    product_uom,
                    product_uom_qty,
                    company_id,
                    remarks,
                    location_id,
                    partner_id,
                    state,
                    purchase_line_id,
                    from_cake_location,
                    date_expected,
    --                string_availability_info,
                    reason_of_reverse,
                    move_dest_id,
                    date,
                    procure_method,
                    group_id,
                    name,
                    picking_type_id,
                    picking_id,
                    location_dest_id,
                    product_id,
                    priority,
                    product_qty,
                    request_id,
                    request_line_id,
                    is_dispute_move,
                    is_accept_dispute,
                    is_reject_dispute,
                    is_disagree_dispute,
                    adjusted_dispute_qty,
                    initial_move_qty        
                from stock_move

            )""")


class DisputeMovesConfirm(models.TransientModel):
    """
            This wizard will take action on stock_picking based on the action assigned to the selected lines.
    """

    _name = 'dispute.move.confirm'
    _description = 'Confirm Dispute Moves'

    @api.multi
    def validate_picking(self, picking):
        """
        run a series of action on stock_picking to validate that picking
        :param picking: a picking which is going to be validated
        :return:
        """
        self.ensure_one()
        if picking.move_lines:
            picking.action_assign()
            picking.do_new_transit()
            picking.do_transit()
            picking.do_process_transfer_done()

    @api.multi
    def reject_move(self, picking, moves):
        """
        create a backorder for the lines which are going to be rejected
        :param picking: the picking contains the rejected lines
        :param moves: the moves which are related to the rejected lines
        :return:
        """
        self.ensure_one()
        backorder_id = picking.copy({
            'name': '/',
            'move_lines': [],
            'pack_operation_ids': [],
            'backorder_id': picking.id
        })
        for move in moves:
            # change the stock move picking id to the backorder
            move_obj = self.env['stock.move'].search([('id', '=', move)])
            move_obj.write({'picking_id': backorder_id.id})
        backorder_id.action_cancel()

    @api.multi
    def amend_stock_move_qty(self, move, qty):
        """
        amend the stock move quantity based on the quantity provided
        :param move: the stock move which is disagreed
        :param qty: new quantity
        :return:
        """
        self.ensure_one()
        move.product_uom_qty = abs(qty)

    @api.multi
    def get_move_picking(self, moves):
        """
        remove the redundant pickings and return pickings which are related to the moves
        :param moves: the stock moves which are selected
        :return: stock picking
        """
        pickings = [move.picking_id for move in moves]
        picks = list(set(pickings))
        return picks

    @api.multi
    def confirm_dispute_moves(self):
        """
        perform the action on the stock picking and stock move
        :return:
        """
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        stock_move_obj = self.env['stock.move']
        stock_move_report_obj = self.env['stock.move.report']
        # get the selected stock_move_report object
        move_ids = stock_move_obj.browse(active_ids)
        move_report_ids = stock_move_report_obj.browse(active_ids)
        # get all the stock moves which belong to the dispute picking and relates to the outlet ordering
        full_move_ids = stock_move_report_obj.search(
            [('request_id', '=', move_ids[0].request_id.id), ('is_dispute_move', '=', True),
             ('state', '=', 'draft')])
        # check any transfer line is missed out
        for move in full_move_ids:
            if move.id not in active_ids:
                raise UserError(_('Please select all the dispute moves of the transfer request.'))

        if move_report_ids:
            move_report_ids.check_dispute_action()

        if all([move.is_accept_dispute for move in move_ids]):
            # validate all the pickings with original dispute quantity
            pickings = self.get_move_picking(move_ids)
            if pickings:
                for pick in pickings:
                    self.validate_picking(pick)

        elif all(move.is_reject_dispute for move in move_ids):
            # cancel all the pickings
            pickings = self.get_move_picking(move_ids)
            if pickings:
                for pick in pickings:
                    pick.action_cancel()

        elif all(move.is_disagree_dispute for move in move_ids) or all(
                move.is_accept_dispute or move.is_disagree_dispute for move in move_ids):
            # if the dispute is disagreed, amend the stock move quantity and validate it
            pickings = self.get_move_picking(move_ids)

            for move in move_ids:
                if move.is_disagree_dispute:
                    self.amend_stock_move_qty(move, move.adjusted_dispute_qty)

            if pickings:
                for pick in pickings:
                    self.validate_picking(pick)

        elif all(move.is_accept_dispute or move.is_reject_dispute for move in move_ids):
            # create backorder for rejected stock move and cancel the backorder, validate the remaining accepted moves
            pickings = self.get_move_picking(move_ids)

            if pickings:
                for pick in pickings:
                    if all(move.is_reject_dispute for move in move_ids for ml in pick.move_lines if move.id == ml.id):
                        pick.action_cancel()
                        continue
                    # get the rejected move
                    backorder_move = []
                    if pick.move_lines:
                        backorder_move = [move.id for move in move_ids for ml in pick.move_lines
                                          if move.is_reject_dispute and move.id == ml.id]
                    if backorder_move:
                        self.reject_move(pick, backorder_move)
                    self.validate_picking(pick)

        elif all(move.is_reject_dispute or move.is_disagree_dispute for move in move_ids) or all(
                move.is_accept_dispute or move.is_reject_dispute or move.is_disagree_dispute for move in move_ids):
            # create backorder for rejected stock move and cancel it, amend the disagreed quantity and validate disagreed and accepted.
            pickings = self.get_move_picking(move_ids)

            for move in move_ids:
                if move.is_disagree_dispute:
                    self.amend_stock_move_qty(move, move.adjusted_dispute_qty)

            if pickings:
                for pick in pickings:
                    if all(move.is_reject_dispute for move in move_ids for ml in pick.move_lines if move.id == ml.id):
                        pick.action_cancel()
                        continue
                    backorder_move = []
                    if pick.move_lines:
                        backorder_move = [move.id for move in move_ids for ml in pick.move_lines
                                          if move.is_reject_dispute and move.id == ml.id]
                    if backorder_move:
                        self.reject_move(pick, backorder_move)
                    self.validate_picking(pick)


class DisputeMoveDummy(models.TransientModel):

    _name = 'dispute.move.dummy'
    _description = 'Dispute Move Dummy'

    move_ids = fields.Many2one('stock.move.report', string='Dispute Move')
    action_ids = fields.Many2one('dispute.move.action', string='Dispute Move Action')
    request_name = fields.Char(string="Request Transfer", required=True)
    picking_name = fields.Char(string="Picking")
    product_name = fields.Char(string="Product")
    uom_name = fields.Char(string="Unit of Measure")
    delivered_qty = fields.Float(string="Delivered Qty")
    dispute_qty = fields.Float(string="Product Dispute Qty")
    product_uom_qty = fields.Float(string='Move Qty')
    accept_dispute = fields.Boolean(string='Accept Dispute')
    reject_dispute = fields.Boolean(string='Reject Dispute')
    disagree_dispute = fields.Boolean(string='Disagree Dispute')
    adjusted_dispute_qty = fields.Float(string='Adjusted Dispute Qty')
    source_location = fields.Many2one(comodel_name="stock.location", string="Source Location")
    dest_location = fields.Many2one(comodel_name="stock.location", string="Destination Location")

    @api.constrains('disagree_dispute', 'adjusted_dispute_qty')
    def check_adjusted_qty_zero(self):
        if self.disagree_dispute and self.adjusted_dispute_qty <= 0:
            raise ValidationError(_('Adjusted Move Quantity should not less than or equal to zero in product: \'%s\'.' % self.product_name))

    @api.onchange('accept_dispute')
    def _onchange_accept_dispute(self):
        if self.accept_dispute:
            self.reject_dispute = False
            self.disagree_dispute = False
            self.adjusted_dispute_qty = 0

    @api.onchange('reject_dispute')
    def _onchange_reject_dispute(self):
        if self.reject_dispute:
            self.accept_dispute = False
            self.disagree_dispute = False
            self.adjusted_dispute_qty = 0

    @api.onchange('disagree_dispute')
    def _onchange_disagree_dispute(self):
        if self.disagree_dispute:
            self.accept_dispute = False
            self.reject_dispute = False
        self.adjusted_dispute_qty = 0


class DisputeMoveAction(models.TransientModel):
    """
        This wizard allows the user to edit the action of all the selected dispute products.
    """
    _name = 'dispute.move.action'
    _description = 'Edit Dispute Moves Action'

    move_ids = fields.One2many('dispute.move.dummy', 'action_ids', string="Dispute Moves", default=lambda self: self.get_lines())

    @api.model
    def get_lines(self):
        """
        return the selected moves to the wizard and raise an error if the moves is not in draft state
        :return: stock.move.report
        """
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        active_dispute_move = self.env['stock.move.report'].browse(active_ids)
        dummy_moves = []

        if any([move.state != 'draft' for move in active_dispute_move]):
            raise UserError(_('Cannot assign action for the Stock Moves which are not in Draft state.'))

        for dispute_move in active_dispute_move:
            dummy_moves.append((0, 0, {
                'move_ids': dispute_move.id,
                'request_name': dispute_move.request_id.name,
                'picking_name': dispute_move.picking_id.name,
                'source_location': dispute_move.location_id,
                'dest_location': dispute_move.location_dest_id,
                'product_name': dispute_move.product_id.name,
                'uom_name': dispute_move.product_uom.name,
                'delivered_qty': dispute_move.request_delivered_qty,
                'dispute_qty': dispute_move.request_line_id.dispute_qty,
                'product_uom_qty': dispute_move.product_uom_qty,
                'accept_dispute': dispute_move.is_accept_dispute,
                'reject_dispute': dispute_move.is_reject_dispute,
                'disagree_dispute': dispute_move.is_disagree_dispute,
                'adjusted_dispute_qty': dispute_move.adjusted_dispute_qty
            }))

        return dummy_moves

    @api.multi
    def save_action(self):
        dispute_move = self.env['stock.move.report']

        for move in self.move_ids:
            dispute_move = dispute_move.browse(move.move_ids.id)
            dispute_move.write({
                'is_accept_dispute': move.accept_dispute,
                'is_reject_dispute': move.reject_dispute,
                'is_disagree_dispute': move.disagree_dispute,
                'adjusted_dispute_qty': move.adjusted_dispute_qty
            })
        return {'type': 'ir.actions.act_window_close'}