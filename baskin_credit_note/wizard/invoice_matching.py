from openerp import models, fields, api, _
from openerp.tools.safe_eval import safe_eval as eval
from openerp.exceptions import UserError
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class InvoiceMatchingAllocation(models.TransientModel):
    _name = "invoice.matching.allocation"
    
    invoice_matching_id = fields.Many2one('invoice.matching', string="Matching Invoice")
    invoice_id = fields.Many2one('account.invoice', string="Invoice", required=True, readonly=True)
    date_invoice = fields.Date(string='Invoice Date', readonly=True)
    number = fields.Char(string="Inv No", readonly=True)
    invoice_amount = fields.Float('Inv Amount', readonly=True)
    amount_due = fields.Float('Amount Due', readonly=True)
    product_id = fields.Many2one('product.product', string="Product", required=True)
    reason = fields.Char('Reason', required=True)
    refund_amount_allocation = fields.Float('Refund Amount Allocation')
    
    
class InvoiceMatching(models.TransientModel):
    _name = "invoice.matching"
    
    invoice_allocation_ids = fields.One2many("invoice.matching.allocation", "invoice_matching_id", string="Invoice Allocation")
    
    @api.model
    def default_get(self, fields):
        rec = super(InvoiceMatching, self).default_get(fields)
        company_id = self.env['res.users']._get_company()
        company = self.env['res.company'].browse(company_id)
        refund_product = company and company.bulk_refund_product.id or False
        if self.env.context.get('invoice_ids'):
            lines = []
            for invoice in self.env['account.invoice'].browse(self.env.context.get('invoice_ids')):
                vals = {'invoice_id' : invoice.id,
                        'date_invoice' : invoice.date_invoice,
                        'number' : invoice.number,
                        'invoice_amount' : invoice.amount_total,
                        'product_id' : refund_product,
                        'amount_due' : invoice.residual}
                lines.append((0,0,vals))
            rec['invoice_allocation_ids'] = lines
        return rec
    
    @api.multi
    def invoice_refund_reconcile(self):
        for inv_line in self.invoice_allocation_ids:
            if not inv_line.refund_amount_allocation:
                raise UserError("Please select Refund Amount Allocation for all lines !")
                
        today_date = datetime.strftime(datetime.now(), DEFAULT_SERVER_DATE_FORMAT)
        for inv_line in self.invoice_allocation_ids:
            refund = inv_line.invoice_id.refund(today_date, False, inv_line.reason, inv_line.invoice_id.journal_id.id)
            update_vals = {'name': inv_line.product_id.partner_ref or '' + '\n' + inv_line.product_id.description_sale or '',
                           'product_id':inv_line.product_id.id,
                           'price_unit':inv_line.refund_amount_allocation,
                           'quantity':1}
            if len(refund.invoice_line_ids) == 1:
                refund.invoice_line_ids[0].write(update_vals)
            else:
                update_first = False
                for ref_line in refund.invoice_line_ids:
                    if update_first:
                        ref_line.unlink()
                    else:
                        ref_line.write(update_vals)
                        update_first = True
                   
            refund.compute_taxes()
            refund.signal_workflow('invoice_open')
            
        return True
        
            
            
    