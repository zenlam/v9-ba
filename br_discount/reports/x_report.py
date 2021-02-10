from openerp import models, api, _


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.multi
    def get_x_report_data(self):
        res = super(PosSession, self).get_x_report_data()
        redemption_amount = 0
        for session in self:
            for order in session.order_ids:
                total_on_site = 0
                total_payment = 0
                for stm in order.statement_ids:
                    if stm.journal_id.payment_type == 'on_site':
                        total_on_site += stm.amount
                    total_payment += stm.amount
                # total_voucher_value = 0
                # for voucher_detail in order.sale_voucher_ids:
                #     voucher_value = voucher_detail.value + voucher_detail.unredeem_value
                #     total_voucher_value += voucher_value
                #     tax_ids = voucher_detail.tax_account_id.tax_ids
                #     # TODO: should cover multiple taxes case
                #     tax_amount = tax_ids[-1].amount if tax_ids else 0
                #     redemption_amount += voucher_value + round(voucher_value * tax_amount/(1+tax_amount), 2)
                # # Redemption voucher should be ignore
                # if total_voucher_value >= order.origin_total:
                #     res['ticket_count'] -= 1
        sales_wo_redemption = res['total_net_sale'] * res['total_on_site'] / res['total_sale'] if res['total_sale'] > 0 else 0
        ticket_avg_wo_redemption = sales_wo_redemption / res['ticket_count'] if res['ticket_count'] else 0
        res.update(
            sales_wo_redemption=sales_wo_redemption,
            ticket_avg_wo_redemption=ticket_avg_wo_redemption
        )
        return res
