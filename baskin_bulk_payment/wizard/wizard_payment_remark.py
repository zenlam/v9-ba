
from openerp import api, fields, models


class WizardPaymentRemark(models.TransientModel):
    _name = 'wizard.payment.remark'

    remarks = fields.Text('Remarks', required=True)

    @api.multi
    def apply(self):
        self.ensure_one()
        if self._context.get('active_id'):
            payment = self.env['account.payment'].browse(self._context.get('active_id'))
            payment.write({'authorizer_remarks': self.remarks})
            payment.post()
        return True
