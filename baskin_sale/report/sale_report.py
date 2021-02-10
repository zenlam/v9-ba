from openerp import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    partner_shipping_id = fields.Many2one('res.partner', 'Delivery Point', readonly=True)
    campaign_id = fields.Many2one('utm.campaign', 'Campaign', readonly=True)
    source_id = fields.Many2one('utm.source', 'Source', readonly=True)
    medium_id = fields.Many2one('utm.medium', 'Medium', readonly=True)


    def _select(self):
        res = super(SaleReport,self)._select()
        select_str = res+""" ,s.partner_shipping_id as partner_shipping_id
                             ,s.campaign_id as campaign_id
                             ,s.source_id as source_id
                             ,s.medium_id as medium_id"""
        return select_str
    
    def _group_by(self):
        res = super(SaleReport,self)._group_by()
        group_by_str = res+""" ,s.partner_shipping_id
                               ,s.campaign_id
                               ,s.source_id
                               ,medium_id"""
        return group_by_str