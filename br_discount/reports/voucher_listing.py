# -*- coding: utf-8 -*-

from openerp import models, fields, api, tools
from openerp import models, fields, api, SUPERUSER_ID, _


class br_voucher_listing(models.Model):
    _name = 'br.voucher.listing'
    _auto = False

    company_id = fields.Many2one('res.company', readonly=True)
    promotion_name = fields.Char(string='Discount Name', readonly=True)
    promotion_code = fields.Char(string='Code', readonly=True)
    voucher_code = fields.Char(string='Voucher Code', readonly=True)
    voucher_validation_code = fields.Char(string='Voucher Validation Code',
                                          readonly=True)
    partner_id = fields.Char(string='Customer', readonly=True)
    start_date = fields.Date(string='Start Date', readonly=True)
    end_date = fields.Date(string='End Date', readonly=True)
    date_red = fields.Date(string='Date Redeemed', readonly=True)
    status = fields.Selection(
        [('available', 'Available'), ('expired', 'Expired'),
         ('redeemed', 'Redeemed')], 'Status',
        readonly=True)
    validation_code = fields.Char(string='Validation Code', readonly=True)
    sequence = fields.Integer(string='Sequence', readonly=True)
    order_id = fields.Char(string='Pos order', readonly=True)
    remarks = fields.Char(string='Remarks', readonly=True)
    approval_no = fields.Char(string='Approval No', readonly=True)
    c_uid = fields.Char(string="Created by", readonly=True)
    c_date = fields.Datetime(string="Create Date", readonly=True)
    outlet_name = fields.Char(string='Outlet Name', readonly=True)

    # if you want to inherit this method,
    # then remember to put the comma at the beginning of your inherit function
    def select(self):
        select_query = """
                        bcv.id,
                        bbp.real_name AS promotion_name,
                        bbp.company_id AS company_id,
                        bbp.code AS promotion_code,
                        bcv.voucher_code,
                        rp.name AS partner_id,
                        bcv.start_date,
                        bcv.end_date,
                        bcv.date_red,
                        bcv.status,
                        bcv.validation_code,
                        bcv.voucher_validation_code,
                        bcv.sequence,
                        po.name AS order_id,
                        bmoo.name AS outlet_name,
                        bcv.remarks,
                        bcv.approval_no,
                        rpp.name AS c_uid,
                        bcv.create_date AS c_date
                        """
        return select_query

    def from_query(self):
        from_query = """
                    br_config_voucher bcv
                    LEFT JOIN br_bundle_promotion bbp
                    ON bcv.promotion_id = bbp.id
                    LEFT JOIN res_partner rp
                    ON bcv.partner_id = rp.id
                    LEFT JOIN res_users rs
                    ON bcv.create_uid = rs.id
                    LEFT JOIN res_partner rpp
                    ON rs.partner_id = rpp.id
                    LEFT JOIN pos_order po
                    ON bcv.order_id = po.id
                    LEFT JOIN br_multi_outlet_outlet bmoo
                    ON po.outlet_id = bmoo.id
                    """
        return from_query

    def get_query(self, args):
        query = """
        CREATE or REPLACE VIEW br_voucher_listing as (
            SELECT
                {select}
            FROM
                {from}
            )
        """.format(**args)
        return query

    def init(self, cr):
        print
        "--------> init of voucher listing--------"
        tools.drop_view_if_exists(cr, 'br_voucher_listing')
        statements = {
            'select': self.select(),
            'from': self.from_query(),
        }
        query = self.get_query(statements)
        cr.execute(query)

br_voucher_listing()
