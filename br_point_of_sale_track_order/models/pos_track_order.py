from openerp import models, api, fields

REASONS = [
    ('cancel', 'Cancel Receipt'),
    ('delete', 'Delete Menu Name'),
    ('destroy', 'Destroy Transaction'),
    ('card', 'Manual Credit Card'),
    ('back', 'Back Button')
]


class POSTrackOrder(models.Model):
    _name = "pos.track.order"

    outlet_id = fields.Many2one(string="Outlet", comodel_name="br_multi_outlet.outlet")
    pos_user = fields.Many2one(string="User", comodel_name="res.users")
    invoice_no = fields.Char(string="Invoice No", index=True)
    reference = fields.Char(string="Reference")
    date = fields.Datetime(string='Date')
    # reason = fields.Char(string="Reason")
    line_ids = fields.One2many(comodel_name='pos.track.order.line', inverse_name='track_order_id')

    @api.model
    def create_from_ui(self, logs, storage):
        """
        Create actvitiy track log on POS screen
        :param logs: log data  (list)
        :param storage: localStorage name/key (str)
        :return: storage (str)
        """
        submitted = [o['reference'] for o in logs]
        existing_logs = self.search([('reference', 'in', submitted)])
        existing_references = set([o.invoice_no for o in existing_logs])
        logs_to_save = [o for o in logs if o['reference'] not in existing_references]
        self.process_log(logs_to_save)
        # Return storage name to clear it on browser localStorage
        return storage

    def process_log(self, logs):
        trace_orderline = self.env['pos.track.order.line']
        for log in logs:
            # log from same order should go to 1 track order
            pos_order = self.search([('invoice_no', '=', log['invoice_no'])])
            lines = log['lines']
            if pos_order:
                order_id = pos_order[0].id
                for l in log['lines']:
                    l.update(track_order_id=order_id)
                    trace_orderline.create(l)
            else:
                log.update({
                    'line_ids': [(0, 0, l) for l in lines]
                })
                self.create(log)


class PosTrackOrderLine(models.Model):
    _name = "pos.track.order.line"

    track_order_id = fields.Many2one(comodel_name='pos.track.order')
    product_id = fields.Many2one(comodel_name='product.product', string="Product")
    unit_price = fields.Float(string="Unit Price", digits=(18, 2))
    quantity = fields.Float(string="Quantity", digits=(18, 2))
    reason = fields.Selection(selection=REASONS)
    date_log = fields.Datetime(string="Date Log")
    cashier_id = fields.Many2one(string="Cashier", comodel_name='res.users')
    remark = fields.Char(string="Remark")