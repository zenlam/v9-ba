from openerp import models, api, fields


class BRPosSession(models.Model):
    _inherit = "pos.session"

    @api.multi
    def wkf_action_close(self):
        res = None
        for pos_session in self:
            order_ids = pos_session.order_ids.filtered(lambda r: r.state == 'paid')
            tax_adjustments = order_ids.cal_tax_adjustment(order_tax=order_ids.get_pos_order_tax())
            company_id = pos_session.config_id.company_id.id
            res = super(BRPosSession, self.with_context(TAX_ADJUSTMENTS=tax_adjustments, COMPANY_ID=company_id)).wkf_action_close()
        return res


BRPosSession()


class BRPosOrder(models.Model):
    _inherit = "pos.order"

    tax_adjustment = fields.Float(compute="_compute_tax_adjustment", string="Taxes Adjustment", store=True)

    @api.model
    def _prepare_analytic_account(self, line):
        return line.order_id.outlet_id.analytic_account_id.id

    @api.model
    def get_tax_rule(self, amount, tax_amount, tax, _round=False):
        if tax.price_include:
            result = amount / (1 + tax_amount * 0.01) * tax_amount * 0.01
        else:
            result = amount * tax_amount * 0.01
        if _round:
            return round(result, 2)
        return result

    @api.multi
    def get_pos_order_tax(self):
        result = {}
        for order in self:
            tax_type = {}
            for line in order.lines:
                taxes = line.tax_ids_after_fiscal_position \
                    if line.tax_ids_after_fiscal_position \
                    else line.tax_ids
                amount = round(line.price_unit * line.qty, 2)
                for tax in taxes:
                    if tax.id not in tax_type:
                        tax_type[tax.id] = {"after": 0, "before": 0, "amount": tax.amount}
                    _tax_type = tax_type.get(tax.id)
                    _tax_type['after'] += amount
                    _tax_type['before'] = _tax_type['before'] + order.get_tax_rule(amount, tax.amount, tax, _round=True)
            result[order.id] = tax_type
        return result

    @api.model
    def cal_tax_adjustment(self, order_tax={}):
        taxobj = self.env['account.tax']
        tax_type = {}
        for _k_order in order_tax.keys():
            tax_in_order = order_tax.get(_k_order)
            for _k_tax in tax_in_order:
                tax = tax_in_order[_k_tax]
                tax_type[_k_tax] = tax_type.get(_k_tax, 0) + (self.get_tax_rule(tax['after'], tax['amount'], taxobj.browse(_k_tax), _round=True)
                                                              - tax['before'])
        return tax_type

    @api.multi
    @api.depends('fiscal_position_id', 'lines.tax_ids')
    def _compute_tax_adjustment(self):
        taxobj = self.env['account.tax']
        taxes = self.get_pos_order_tax()
        for order in self:
            tax_type = taxes.get(order.id, {})
            total_tax = 0
            for _key in tax_type:
                tax = tax_type[_key]
                total_tax += self.get_tax_rule(tax['after'], tax['amount'], taxobj.browse(_key), _round=True)
            order.tax_adjustment = round(total_tax - order.amount_tax, 2)

    @api.multi
    def _create_account_move_line(self, session=None, move_id=None):
        analytic_account_id = self[0].outlet_id.analytic_account_id.id
        res = super(BRPosOrder, self.with_context(ANALYTIC_ACCOUNT=analytic_account_id))._create_account_move_line(
            session=session, move_id=move_id)
        return res

    @api.multi
    def action_post(self):
        tax_adjustments = self.cal_tax_adjustment(order_tax=self.get_pos_order_tax())
        return super(BRPosOrder, self.with_context(TAX_ADJUSTMENTS=tax_adjustments)).action_post()


BRPosOrder()
