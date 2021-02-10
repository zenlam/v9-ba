from openerp import models, fields, api, SUPERUSER_ID, _
from datetime import date, datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from dateutil import relativedelta


class br_stock_location_path(models.Model):
    _inherit = 'stock.location.path'

    @api.model
    def _prepare_push_apply(self, rule, move):
        newdate = (datetime.strptime(move.date_expected, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta.relativedelta(
            days=rule.delay or 0)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        # vannh get analytic_account_id
        analytic_account_id = rule.location_dest_id.br_analytic_account_id and rule.location_dest_id.br_analytic_account_id.id or False
        if not analytic_account_id:
            des_location = rule.location_dest_id
            parent_location = des_location.location_id
            while parent_location:
                ls_wh = self.env['stock.warehouse'].search(([
                                                            ('code', '=', parent_location.name)
                                                            ]))
                for wh in ls_wh:
                    ls_outlet = self.env['br_multi_outlet.outlet'].search(([
                                                            ('warehouse_id', '=', wh.id)
                                                                            ]))
                    for outlet in ls_outlet:
                        if outlet.analytic_account_id:
                            analytic_account_id = outlet.analytic_account_id.id or False
                parent_location = parent_location.location_id
        # vannh get analytic_account_id

        return {
            'origin': move.origin or move.picking_id.name or "/",
            'location_id': move.location_dest_id.id,
            'location_dest_id': rule.location_dest_id.id,
            'date': newdate,
            'company_id': rule.company_id and rule.company_id.id or False,
            'date_expected': newdate,
            'picking_id': False,
            'picking_type_id': rule.picking_type_id and rule.picking_type_id.id or False,
            'propagate': rule.propagate,
            'push_rule_id': rule.id,
            'warehouse_id': rule.warehouse_id and rule.warehouse_id.id or False,
            'account_analytic_id': analytic_account_id
        }