from openerp import models, api, fields, _


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def get_tax_summary(self):
        """Get GST Summary"""
        self.ensure_one()
        taxes = {}

        for line in self.lines:
            for tax in line.tax_ids_after_fiscal_position:
                if tax.price_include:
                    tax_amount = round(round(line.price_unit * line.qty, 2) / (1 + tax.amount / 100) * (tax.amount / 100), 2)
                    total_amount = round(round(line.price_unit * line.qty, 2) / (1 + tax.amount / 100), 2)
                else:
                    tax_amount = round(round(line.price_unit * line.qty, 2) * (tax.amount / 100), 2)
                    total_amount = round(round(line.price_unit * line.qty, 2), 2)
                if tax.id not in taxes:
                    taxes[tax.id] = {
                        'tax_code': tax.tax_code,
                        'tax_rate': tax.amount,
                        'total_w_tax': total_amount,
                        'tax_amount': tax_amount
                    }
                else:
                    taxes[tax.id]['total_w_tax'] += total_amount
                    taxes[tax.id]['tax_amount'] += tax_amount
        return taxes