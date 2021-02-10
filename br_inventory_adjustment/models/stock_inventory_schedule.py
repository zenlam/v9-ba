from openerp import models, api, fields, _
from datetime import datetime, timedelta
from openerp.exceptions import ValidationError
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import traceback

LOG_STATUS = [('done', 'Done'), ('failed', 'Failed')]


class StockInventorySchedule(models.Model):
    _name = 'stock.inventory.schedule'

    name = fields.Char(string="Schedule Name")
    line_ids = fields.One2many(comodel_name='stock.inventory.schedule.line', string="Details", inverse_name='schedule_id')
    log_ids = fields.One2many(comodel_name='stock.inventory.schedule.log', string="Logs", inverse_name='schedule_id')

    @api.multi
    def run(self):
        log_obj = self.env['stock.inventory.schedule.log']
        schedule_date = self.env.context.get('schedule_date', None)
        for schedule in self:
            log_vals = {'schedule_id': schedule.id, 'date_start': datetime.now()}
            details = []
            lines = self.line_ids.filtered(lambda x: x.date == schedule_date) if schedule_date else self.line_ids
            for line in lines:
                if line.template_id.active:
                    detail = {
                        'template_id': line.template_id.id,
                        'date': line.date,
                        'state': 'done'
                    }
                    try:
                        inventory = line.generate_inventory()
                        inventory.prepare_inventory()
                    except Exception as e:
                        tb = traceback.format_exc()
                        detail.update(state='failed', detail=tb)
                    details.append((0, 0, detail))
            log_vals.update(detail_ids=details, date_end=datetime.now())
            log_obj.create(log_vals)

    @api.multi
    def action_run_schedule(self):
        date = (datetime.now() + timedelta(hours=8)).date().strftime(DEFAULT_SERVER_DATE_FORMAT)
        self.with_context(schedule_date=date).run()

    @api.one
    @api.constrains('line_ids')
    def check_line_ids(self):
        temp = []
        for l in self.line_ids:
            key = (l.date, l.template_id.id)
            if key in temp:
                raise ValidationError(_("You have duplication in schedule line !"))
            temp.append(key)


class StockInventoryScheduleLine(models.Model):
    _name = "stock.inventory.schedule.line"

    schedule_id = fields.Many2one(comodel_name='stock.inventory.schedule', string="Schedule", ondelete='restrict')
    date = fields.Date("Schedule Date")
    template_id = fields.Many2one(comodel_name="stock.inventory.template", string="Template")
    active = fields.Boolean(string="Active", related="template_id.active")

    @api.multi
    def generate_inventory(self):
        inventories = self.env['stock.inventory']
        for line in self:
            for warehouse in line.template_id.warehouse_ids:
                inventory_template = line.template_id
                inventory_date = datetime.strptime(line.date + ' 00:00:00', DEFAULT_SERVER_DATETIME_FORMAT) - timedelta(hours=8)
                vals = inventory_template.with_context(inventory_date=inventory_date)._prepare_inventory_value(warehouse)
                inventories |= self.env['stock.inventory'].create(vals)
        return inventories


class StockInventoryScheduleLog(models.Model):
    _name = "stock.inventory.schedule.log"
    _rec_name = 'schedule_id'
    _order = 'date_start DESC'

    schedule_id = fields.Many2one(comodel_name="stock.inventory.schedule", string="Schedule")
    date_start = fields.Datetime(string="Start At")
    date_end = fields.Datetime(string="End At")
    state = fields.Selection(selection=LOG_STATUS, string="Status", compute="_get_state")
    detail_ids = fields.One2many(string="Details", comodel_name="stock.inventory.schedule.log.line", inverse_name='log_id')

    @api.multi
    def _get_state(self):
        for log in self:
            if all([x.state == 'done' for x in log.detail_ids]):
                log.state = 'done'
                continue
            if any([x.state == 'failed' for x in log.detail_ids]):
                log.state = 'failed'
                continue


class StockInventoryScheduleLogLine(models.Model):
    _name = "stock.inventory.schedule.log.line"

    log_id = fields.Many2one(comodel_name='stock.inventory.schedule.log', string="Log")
    state = fields.Selection(selection=LOG_STATUS, string="Status")
    template_id = fields.Many2one(comodel_name="stock.inventory.template")
    date = fields.Date(string="Date")
    detail = fields.Text(string="Detail")
