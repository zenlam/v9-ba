from openerp import fields, models, api, _
from datetime import datetime
import pytz
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError


DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def convert_timezone(from_tz, to_tz, dt):
    from_tz = pytz.timezone(from_tz).localize(datetime.strptime(dt, DATETIME_FORMAT))
    to_tz = from_tz.astimezone(pytz.timezone(to_tz))
    return to_tz.strftime(DATETIME_FORMAT)


class InventoryDetailsReport(models.TransientModel):
    _name = 'inventory.details.report'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    warehouse_type = fields.Selection([('outlet_wh', 'Outlet Warehouses'), ('hq_wh', 'HQ Warehouses')])
    transit_loc = fields.Boolean(string="Transit Location", default=False)
    warehouse_ids = fields.Many2many(string="Warehouse", comodel_name='stock.warehouse')
    location_ids = fields.Many2many(string="Location", comodel_name='stock.location')
    product_categ_ids = fields.Many2many(string='Product Category', comodel_name='product.category')
    product_ids = fields.Many2many(string='Product', comodel_name='product.template')
    period = fields.Selection([('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly')],string="Period", default='daily')
    uom_type = fields.Selection([('standard', 'Standard'),('distribution', 'Distribution'), ('storage', 'Storage')], default='distribution')
    report_type = fields.Selection([('balance', 'Balance'), ('movement', 'Movement')], default='balance')

    @api.multi
    def action_print(self):
        # perform flush date checking before printing the report
        self.check_flush_date()
        if self.report_type == 'balance':
            return self.env['report'].get_action(self, 'inventory.details.balance')
        elif self.report_type == 'movement':
            return self.env['report'].get_action(self, 'inventory.details.movement')

    @api.multi
    def check_flush_date(self):
        """
        Make sure the start date of the report is greater than latest flush
        date
        """
        for res in self:
            # get the latest flush date
            latest_flush_date = self.env['stock.flush.date'].search(
                [], order='flush_date desc', limit=1)
            # check the report start date
            # no need to check for the end date since the end_date must be
            # greater than start_date validation is there.
            if latest_flush_date:
                flush_date = convert_timezone(
                    'UTC',
                    self.env.user.tz or 'UTC',
                    latest_flush_date.flush_date).split(' ')[0]
                if res.start_date and \
                        datetime.strptime(res.start_date,
                                          DEFAULT_SERVER_DATE_FORMAT) < \
                        datetime.strptime(flush_date,
                                          DEFAULT_SERVER_DATE_FORMAT):
                    raise UserError(('Kindly select a start date greater '
                                     'than the flush date.\n Flush Date: '
                                     '%s') % flush_date)
            return True

    @api.onchange('warehouse_type')
    def onchange_warehouse_type(self):
        res = {}
        if self.warehouse_type:
            sql = "SELECT warehouse_id FROM br_multi_outlet_outlet"
            self.env.cr.execute(sql)
            outlet_warehouses = [x[0] for x in self.env.cr.fetchall()]
            if self.warehouse_type == 'outlet_wh':
                res = {'domain': {'warehouse_ids': [('id', 'in', outlet_warehouses)]}}
            elif self.warehouse_type == 'hq_wh':
                res = {'domain': {'warehouse_ids': [('id', 'not in', outlet_warehouses)]}}
        return res

    @api.onchange('warehouse_ids')
    def onchange_warehouse_ids(self):
        res = {'domain': {'location_ids':[('usage', '!=', 'view')]}}
        if self.warehouse_ids:
            view_loc = [x.view_location_id.id for x in self.warehouse_ids]
            res = {'domain': {'location_ids': [('id', 'child_of', view_loc)]}}
        return res

    @api.onchange('product_categ_ids')
    def onchange_product_categ_ids(self):
        res = {}
        if self.product_categ_ids:
            res = {'domain': {'product_ids': [('categ_id', 'child_of', [x.id for x in self.product_categ_ids])]}}
        return res

    @api.onchange('transit_loc')
    def onchange_transit_loc(self):
        res = {}
        if self.transit_loc:
            res = {'domain': {'location_ids': [('usage', '=', 'transit')]}}
        else:
            res = self.onchange_warehouse_ids()
        return res
