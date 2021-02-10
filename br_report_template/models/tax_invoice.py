from openerp import models, api, fields, _
from openerp.tools import amount_to_text_en

class br_tax_invoice(models.Model):
    _inherit = 'account.invoice'

    def get_net_total_in_word(self, currency):
        amount_inword = amount_to_text_en.amount_to_text(self.amount_total, 'en', currency)
        amount_inword = amount_inword.replace('%s ' % currency, '')
        return amount_inword

    def get_discount(self):
        discount = 0
        for line in self.invoice_line_ids:
            if line.price_subtotal < 0:
                discount += (-1 * line.price_subtotal)
        return discount

    def get_sale_ob(self):
        ob = None
        if self.origin:
            ob = self.env['sale.order'].search([('name', '=', self.origin)],limit=1)
        return ob

    def get_do_no(self):
        do_no = ''
        sale_ob = self.get_sale_ob()
        if sale_ob:
            procurement_group_id = sale_ob.procurement_group_id
            if procurement_group_id:
                picking_ob = self.env['stock.picking'].search([('group_id', '=', procurement_group_id.id), ('picking_type_id.code', '=', 'outgoing'), ('state', '=', 'done')])
                if picking_ob:
                    do_no = picking_ob[0].name
        return do_no



    remark = fields.Text(string=_("Remark"))
    # po_no = fields.Char(string=_("P/O No"))
    # delivery_date = fields.Date(string=_("Delivery Date"))
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address')
    attn_to = fields.Many2one('res.partner', string='Attn To')


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(br_tax_invoice, self).fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu)

        if res.get('name') == 'account.invoice.form' or res.get('name') == 'account.invoice.tree':
            if res.get('toolbar', False) and res.get('toolbar').get('print', False):
                i = 0
                j = 0
                for report in res['toolbar']['print']:
                    if report['xml_id'] == 'br_report_template.account_invoices_approval':
                        j = i
                    i += 1
                del res['toolbar']['print'][j]
        return res