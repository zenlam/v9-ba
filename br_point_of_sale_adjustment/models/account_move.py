from openerp import fields, models, api


class BRAccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def prepare_move_line_tax_adjustment(self, tax=None, tax_adjustment=0, adjustment_acc=None):
        if tax and tax_adjustment:
            acc_credit = tax.account_id.id
            acc_debit = adjustment_acc
            credit_tax_line_id = tax.id
            credit_tax_ids = [(6, 0, [])]
            debit_tax_line_id = False
            debit_tax_ids = [(6, 0, [tax.id])]
            if tax_adjustment < 0:
                acc_credit = adjustment_acc
                acc_debit = tax.account_id.id
                credit_tax_line_id = False
                credit_tax_ids = [(6, 0, [tax.id])]
                debit_tax_line_id = tax.id
                debit_tax_ids = [(6, 0, [])]
            return [(0, 0, {'name': "Sales-Tax adjustment (Tax %s)" % tax.name,
                            'account_id': acc_credit,
                            'tax_line_id': credit_tax_line_id,
                            'tax_ids': credit_tax_ids,
                            'debit': 0,
                            'credit': abs(tax_adjustment)}),
                    (0, 0, {'name': "Sales-Tax adjustment (Tax %s)" % tax.name,
                            'account_id': acc_debit,
                            'tax_line_id': debit_tax_line_id,
                            'tax_ids': debit_tax_ids,
                            'debit': abs(tax_adjustment),
                            'credit': 0})]
        return []

    @api.multi
    def add_analytic_account_line(self, values):
        if 'ANALYTIC_ACCOUNT' in self.env.context and 'line_ids' in values:
            # write analytic_account_id for tax line
            analytic_account_id = self.env.context.get('ANALYTIC_ACCOUNT')
            for line in values['line_ids']:
                if len(line) >= 2 and not line[2].get('analytic_account_id', False):
                    line[2]['analytic_account_id'] = analytic_account_id

    @api.multi
    def add_adjustment_line(self, values):
        company_obj = self.env['res.company']
        if 'TAX_ADJUSTMENTS' in self.env.context and 'line_ids' in values:
            # add line tax adjustment
            tax_adjustments = self.env.context['TAX_ADJUSTMENTS']
            tax_obj = self.env['account.tax']
            sales_gst_adjustment_acc = company_obj.browse(self.env.context['force_company']).sales_gst_adjustment_acc.id
            for _key in tax_adjustments.keys():
                # add tax adjustment to data
                values['line_ids'].extend(self.prepare_move_line_tax_adjustment(
                                            tax=tax_obj.browse(_key),
                                            tax_adjustment=tax_adjustments[_key],
                                            adjustment_acc=sales_gst_adjustment_acc))

    @api.multi
    def write(self, values):
        self.add_adjustment_line(values)
        self.add_analytic_account_line(values)
        res = super(BRAccountMove, self).write(values)
        return res


BRAccountMove()
