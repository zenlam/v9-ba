from openerp import fields, models, api


class BRAccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def get_grouping_key(self, invoice_tax_val):
        """ Returns a string that will be used to group account.invoice.tax sharing the same properties"""
        res = super(BRAccountTax, self).get_grouping_key(invoice_tax_val)
        if self.env.context.get('ANALYTIC', True):
            res = str(invoice_tax_val['tax_id']) + '-' + str(invoice_tax_val['account_analytic_id'])
        return res

    @api.model
    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None):
        res = super(BRAccountTax, self).compute_all(price_unit, currency=currency, quantity=quantity,
                                                    product=product, partner=partner)
        if self.env.context.get('ANALYTIC', True):
            for tax in res['taxes']:
                tax['analytic'] = True
        return res

BRAccountTax()
