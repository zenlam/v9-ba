from openerp import models, api, fields, _
from openerp.tools import amount_to_text_en
import logging
_logger = logging.getLogger(__name__)

class br_sale_order(models.Model):
    _inherit = 'sale.order'

    def get_net_total_in_word(self, currency):
        amount_inword = amount_to_text_en.amount_to_text(self.amount_total, 'en', currency);
        amount_inword = amount_inword.replace('%s ' % currency, '')
        return amount_inword

    def get_discount(self):
        discount = 0
        for line in self.order_line:
            if line.price_subtotal < 0:
                discount += (-1 * line.price_subtotal)
        return discount

    remark = fields.Text(string=_("Remark"))
    po_no = fields.Char(string=_("Po No."))
    delivery_date = fields.Date(string=_("Delivery Date"))
