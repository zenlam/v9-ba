from openerp import models, api, _
from openerp.exceptions import ValidationError


class BRResCompany(models.Model):
    _inherit = 'res.company'

    @api.multi
    def write(self, values):
        if values.get('fiscalyear_lock_date'):
            nb_draft_entries = self.env['account.move'].search([
                ('company_id', 'in', [c.id for c in self]),
                ('state', '=', 'draft'),
                ('date', '<=', values['fiscalyear_lock_date'])])
            if nb_draft_entries:
                raise ValidationError(_('There are still unposted entries in the period you want to lock. '
                                        'You should either post or delete them.'))
        res = super(BRResCompany, self).write(values)
        return res

BRResCompany()
