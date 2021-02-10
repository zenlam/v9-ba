from openerp import models, api, fields, _


class TransferCancelConfirmation(models.TransientModel):
    _name = 'transfer.cancel.confirmation'

    remark = fields.Text(string="Remark", required=1)

    @api.multi
    def action_cancel(self):
        transfer_ids = self.env.context.get('active_ids', False)
        if transfer_ids:
            transfers = self.env['br.stock.request.transfer'].browse(transfer_ids)
            transfers.action_cancel()
            transfers.write({'remark': self.remark})
