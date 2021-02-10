from openerp import models, api, fields


class BRProductPriceList(models.Model):
    _inherit = "product.pricelist"

    # @api.model
    # def get_all_price_list(self):
    #     price_list = self.search([])
    #     result = {}
    #     for prl in price_list:
    #         result[prl.id] = [x.id for x in prl.item_ids]
    #     return result

    @api.model
    def get_outlet_pricelist(self, pricelist_id):
        price_list = self.browse(pricelist_id)
        result = {}
        for prl in price_list:
            result[prl.id] = [x.id for x in prl.item_ids]
        return result

BRProductPriceList()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pos_categ_id = fields.Many2one('pos.category', 'Point of Sale Category', help="Those categories are used to group similar products for point of sale.", ondelete='restrict', oldname='pos_categ_id')