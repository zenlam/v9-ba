# -*- coding: utf-8 -*-
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from openerp import api, fields, models, registry, _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from openerp.exceptions import Warning as UserError
import logging

_logger = logging.getLogger(__name__)

class AccountAssetAsset(models.Model):
    _inherit = 'account.asset.asset'
    
    invoice_line_id = fields.Many2one('account.invoice.line', string='Invoice Line', copy=False)
    depreciation_val = fields.Float(string='Depreciation Value', compute='get_depreciation_val')
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account',
                                          domain=[('account_type', '=', 'normal')], required=True)

    @api.multi
    def get_depreciation_val(self):
        for asset in self:
            if asset.depreciation_line_ids:
                asset.depreciation_val = asset.depreciation_line_ids[0].amount

    @api.onchange('category_id')
    def onchange_category_id(self):
        res = super(AccountAssetAsset, self).onchange_category_id()
        if self.category_id and self.category_id.account_analytic_id:
            self.account_analytic_id = self.category_id.account_analytic_id.id
        else:
            self.account_analytic_id = False

        return res


    # NOTE : MITESH SAVANI : This method overwrite to set analytic account field for the auto create depreciation line
    @api.multi
    def compute_depreciation_board(self):
        self.ensure_one()

        posted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(key=lambda l: l.depreciation_date)
        unposted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: not x.move_check)

        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

        if self.value_residual != 0.0:
            amount_to_depr = residual_amount = self.value_residual
            if self.prorata:
                depreciation_date = datetime.strptime(self._get_last_depreciation_date()[self.id], DF).date()
            else:
                # depreciation_date = 1st of January of purchase year if annual valuation, 1st of
                # purchase month in other cases
                if self.method_period >= 12:
                    asset_date = datetime.strptime(self.date[:4] + '-01-01', DF).date()
                else:
                    asset_date = datetime.strptime(self.date[:7] + '-01', DF).date()
                # if we already have some previous validated entries, starting date isn't 1st January but last entry + method period
                if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
                    last_depreciation_date = datetime.strptime(posted_depreciation_line_ids[-1].depreciation_date, DF).date()
                    depreciation_date = last_depreciation_date + relativedelta(months=+self.method_period)
                else:
                    depreciation_date = asset_date
            day = depreciation_date.day
            month = depreciation_date.month
            year = depreciation_date.year
            total_days = (year % 4) and 365 or 366

            undone_dotation_number = self._compute_board_undone_dotation_nb(depreciation_date, total_days)

            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                sequence = x + 1
                amount = self._compute_board_amount(sequence, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date)
                amount = self.currency_id.round(amount)
                residual_amount -= amount
                vals = {
                    'amount': amount,
                    'asset_id': self.id,
                    'sequence': sequence,
                    'name': (self.code or '') + '/' + str(sequence),
                    'remaining_value': residual_amount,
                    'depreciated_value': self.value - (self.salvage_value + residual_amount),
                    'depreciation_date': depreciation_date.strftime(DF),
                    'account_analytic_id': self.invoice_line_id and self.invoice_line_id.account_analytic_id.id or self.account_analytic_id.id
                }
                commands.append((0, False, vals))
                # Considering Depr. Period as months
                depreciation_date = date(year, month, day) + relativedelta(months=+self.method_period)
                day = depreciation_date.day
                month = depreciation_date.month
                year = depreciation_date.year

        self.write({'depreciation_line_ids': commands})

        return True
    
    @api.multi
    def open_entries(self):
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': dict(search_default_asset_id=self.id, default_asset_id=self.id),
        }

    @api.multi
    def set_to_close(self):
        move_ids = []
        for asset in self:
            unposted_depreciation_line_ids = asset.depreciation_line_ids.filtered(lambda x: not x.move_check)
            if unposted_depreciation_line_ids:
                old_values = {
                    'method_end': asset.method_end,
                    'method_number': asset.method_number,
                }

                # Remove all unposted depr. lines
                commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

                # Create a new depr. line with the residual amount and post it
                sequence = len(asset.depreciation_line_ids) - len(unposted_depreciation_line_ids) + 1
                today = datetime.today().strftime(DF)
                vals = {
                    'amount': asset.value_residual,
                    'asset_id': asset.id,
                    'sequence': sequence,
                    'name': (asset.code or '') + '/' + str(sequence),
                    'remaining_value': 0,
                    'depreciated_value': asset.value - asset.salvage_value,  # the asset is completely depreciated
                    'depreciation_date': today,
                    'account_analytic_id': asset.account_analytic_id.id,
                }
                commands.append((0, False, vals))
                asset.write({'depreciation_line_ids': commands, 'method_end': today, 'method_number': sequence})
                tracked_fields = self.env['account.asset.asset'].fields_get(['method_number', 'method_end'])
                changes, tracking_value_ids = asset._message_track(tracked_fields, old_values)
                if changes:
                    asset.message_post(subject=_('Asset sold or disposed. Accounting entry awaiting for validation.'),
                                       tracking_value_ids=tracking_value_ids)
                move_ids += asset.depreciation_line_ids[-1].create_move(post_move=False)
        if move_ids:
            name = _('Disposal Move')
            view_mode = 'form'
            if len(move_ids) > 1:
                name = _('Disposal Moves')
                view_mode = 'tree,form'
            return {
                'name': name,
                'view_type': 'form',
                'view_mode': view_mode,
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': move_ids[0],
            }

class AccountAssetDepreciationLine(models.Model):
    _inherit = 'account.asset.depreciation.line'

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', domain=[('account_type', '=', 'normal')], required=False)

    def confirm_depreciation(self, log):
        log_line_obj = self.env['br.account.asset.asset.entry.log.line']
        log_line = log_line_obj.create({
            'log_id': log,
            'asset_id': self.asset_id.id,
            'depreciation_date': self.depreciation_date,
            'depreciation_id': self.id
        })
        try:
            self.create_move()
            log_line.write({'posting_state': 'Success'})
        except Exception as e:
            log_line.write({'posting_state': 'Failed ' + str(e)})
        self.env.cr.commit()

    # NOTE : MITESH SAVANI : this method over write to set the analytic account to move line from the depreciation line.
    @api.multi
    def create_move(self, post_move=True):
        created_moves = self.env['account.move']
        for line in self:
            if not line.account_analytic_id:
                raise UserError("Analytic account is required on Asset Depreciation Line !")
            depreciation_date = self.env.context.get('depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
            company_currency = line.asset_id.company_id.currency_id
            current_currency = line.asset_id.currency_id
            amount = current_currency.compute(line.amount, company_currency)
            sign = (line.asset_id.category_id.journal_id.type == 'purchase' or line.asset_id.category_id.journal_id.type == 'sale' and 1) or -1
            asset_name = line.asset_id.name + ' (%s/%s)' % (line.sequence, line.asset_id.method_number)
            reference = line.asset_id.code
            journal_id = line.asset_id.category_id.journal_id.id
            partner_id = line.asset_id.partner_id.id
            categ_type = line.asset_id.category_id.type
            #debit_account = line.asset_id.category_id.account_asset_id.id
            #credit_account = line.asset_id.category_id.account_depreciation_id.id
            debit_account = line.asset_id.category_id.account_depreciation_id.id
            credit_account = line.asset_id.category_id.account_asset_id.id
            if line.asset_id.type == 'sale':
                debit_account = line.asset_id.category_id.account_asset_id.id
                credit_account = line.asset_id.category_id.account_depreciation_id.id
            move_line_1 = {
                'name': asset_name,
                'account_id': credit_account,
                'debit': 0.0,
                'credit': amount,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'currency_id': company_currency != current_currency and current_currency.id or False,
                'amount_currency': company_currency != current_currency and - sign * line.amount or 0.0,
                'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
#                 'analytic_account_id': line.account_analytic_id.id if categ_type == 'sale' else False,
                'date': depreciation_date,
            }
            move_line_2 = {
                'name': asset_name,
                'account_id': debit_account,
                'credit': 0.0,
                'debit': amount,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'currency_id': company_currency != current_currency and current_currency.id or False,
                'amount_currency': company_currency != current_currency and sign * line.amount or 0.0,
                'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
#                 'analytic_account_id': line.account_analytic_id.id if categ_type == 'purchase' else False,
                'date': depreciation_date,
            }
            move_vals = {
                'ref': reference,
                'date': depreciation_date or False,
                'journal_id': line.asset_id.category_id.journal_id.id,
                'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                'asset_id': line.asset_id.id,
                }
            move = self.env['account.move'].create(move_vals)
            line.write({'move_id': move.id, 'move_check': True})
            created_moves |= move

        if post_move and created_moves:
            created_moves.filtered(lambda r: r.asset_id and r.asset_id.category_id and r.asset_id.category_id.open_asset).post()
        return [x.id for x in created_moves]