# -*- coding: utf-8 -*-
from openerp import api, fields, models, registry, _
from datetime import datetime
from openerp.addons.connector.queue.job import (
    job
)
from openerp.addons.connector.session import (
    ConnectorSession
)

@job
def _generate_asset_entry(session, model_name, asset_ids, date):
    assets = session.env[model_name].browse(asset_ids)
    if assets:
        assets._compute_entries(date)


class AssetDepreciationConfirmationWizard(models.TransientModel):
    _inherit = "asset.depreciation.confirmation.wizard"

    @api.multi
    def asset_compute(self):
        self.ensure_one()
        context = self._context
        assets = self.env['account.asset.asset'].search([('state', '=', 'open'), ('category_id.type', '=', context.get('asset_type'))])
        session = ConnectorSession(self.env.cr, self.env.user.id, context=self.env.context)
        _generate_asset_entry.delay(session, 'account.asset.asset', assets.ids, self.date)
        return True


class AccountAssetAssetEntryLog(models.Model):
    _name = 'br.account.asset.asset.entry.log'
    _description = 'Log file that keep track of entry posting for depreciation asset'
    _order = 'id DESC'

    name = fields.Char(string='Name')
    date = fields.Date(string='Date')
    total_entry = fields.Integer(string='Total Entry Included', compute='compute_entry_details')
    success_entry = fields.Integer(string='Success Posted Entry', compute='compute_entry_details')
    fail_entry = fields.Integer(string='Failed Posted Entry', compute='compute_entry_details')
    log_line_ids = fields.One2many('br.account.asset.asset.entry.log.line', inverse_name='log_id', string='Log Lines')

    def compute_entry_details(self):
        for log in self:
            log.total_entry = len(log.log_line_ids)
            log.success_entry = len([log_line for log_line in log.log_line_ids if log_line.depreciation_id.move_check])
            log.fail_entry = len([log_line for log_line in log.log_line_ids if not log_line.depreciation_id.move_check])

    @api.model
    def create(self, vals):
        if 'date' in vals and vals['date']:
            records = self.env['br.account.asset.asset.entry.log'].search([('date', '=', vals['date'])])
            name = str(vals['date']) + '-' + str(len(records) + 1)
            vals.update({'name': name})
        return super(AccountAssetAssetEntryLog, self).create(vals)


class AccountAssetAssetEntryLogLine(models.Model):
    _name = 'br.account.asset.asset.entry.log.line'
    _description = 'Log line of a depreciation asset entry posting'
    _order = 'posting_state, asset_id ASC'

    log_id = fields.Many2one('br.account.asset.asset.entry.log', string='Depreciation Asset Entry Log')
    asset_id = fields.Many2one('account.asset.asset', string='Depreciation Asset')
    depreciation_id = fields.Many2one('account.asset.depreciation.line', string='Depreciation Asset Line')
    depreciation_date = fields.Date(string='Depreciation Date')
    posting_state = fields.Char(string='Posting State')
    posted = fields.Boolean(related='depreciation_id.move_check', string='Posted?')


class AccountAssetAsset(models.Model):
    _inherit = 'account.asset.asset'

    @api.multi
    def _compute_entries(self, date):
        log_obj = self.env['br.account.asset.asset.entry.log']
        log = log_obj.create({
            'date': datetime.now().date(),
        })
        self.env.cr.commit()
        depreciation_ids = self.env['account.asset.depreciation.line'].search([
            ('asset_id', 'in', self.ids), ('depreciation_date', '<=', date),
            ('move_check', '=', False)])
        for depreciation in depreciation_ids:
            depreciation.confirm_depreciation(log.id)