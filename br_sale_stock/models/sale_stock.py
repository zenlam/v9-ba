from openerp import api, fields, models, _
from openerp.tools import float_compare
from openerp.addons.sale.sale import SaleOrderLine

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _default_warehouse_id(self):
        """
        Override Default Warehouse
        """
        # Sometime user forgot to key in warehouse leading to wrong data since picking type is set by default
        # => no need to default Warehouse anymore
        return None

    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse',
                                   required=False, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                   default=_default_warehouse_id)


class BrSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Won't need to check availability because it's slow down operation
    @api.onchange('product_uom_qty', 'product_uom', 'route_id')
    def _onchange_product_id_check_availability(self):
        return {}

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty(self):
        for inv in self.order_id.invoice_ids:
            if inv.state in ('paid', 'open'):
                warning_mess = {
                    'title': _('Ordered quantity changed!'),
                    'message': _('You are changing order quantity/unit price while your invoice is already validated. Do not forget to manually update the invoice if needed.'),
                }
                return {'warning': warning_mess}
        return super(BrSaleOrderLine, self)._onchange_product_uom_qty()

    @api.model
    def create(self, vals):
        res = super(BrSaleOrderLine, self).create(vals)

        # Find existing invoice and add invoice line to it
        if res.order_id.invoice_ids:
            invoice_line_vals = res._prepare_invoice_line(qty=res.qty_to_invoice)
            invoice_line_vals.update({'invoice_id': res.order_id.invoice_ids[0].id, 'sale_line_ids': [(6, 0, [res.id])]})
            self.env['account.invoice.line'].create(invoice_line_vals)
        return res

    @api.multi
    def write(self, values):
        lines = False
        if 'product_uom_qty' in values:
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            lines = self.filtered(
                lambda r: r.state == 'sale' and float_compare(r.product_uom_qty, values['product_uom_qty'], precision_digits=precision) != 0)
        result = super(SaleOrderLine, self).write(values)

        if 'product_uom_qty' in values or 'price_unit' in values:
            # Update invoice if it still in draft state
            for l in self:
                # Just in case invoice lines belong to different invoices
                for invoice_line in l.invoice_lines:
                    if invoice_line.invoice_id.state == 'draft':
                        invoice_line.write({'quantity': l.product_uom_qty, 'price_unit': l.price_unit})
        if lines:
            lines._action_procurement_create()
        return result

    @api.multi
    def _action_procurement_create(self):
        """
        Create procurements based on quantity ordered. If the quantity is increased, new
        procurements are created. If the quantity is decreased, no automated action is taken.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        new_procs = self.env['procurement.order']  # Empty recordset
        to_cancel_procs = self.env['procurement.order']
        for line in self:
            if line.state != 'sale' or not line.product_id._need_procurement():
                continue
            qty = 0.0
            line_procs = self.env['procurement.order']
            done_qty = 0.0
            for proc in line.procurement_ids:
                qty += proc.product_qty
                line_procs += proc
                if proc.state == 'done':
                    done_qty += proc.product_qty
            is_equal_qty = float_compare(qty, line.product_uom_qty, precision_digits=precision)
            if is_equal_qty >= 0:
                # Create new procurement then cancel old procurements
                if is_equal_qty > 0 and line_procs:
                    vals = line._prepare_order_line_procurement(group_id=line.order_id.procurement_group_id.id)
                    vals['product_qty'] -= done_qty
                    vals['account_analytic_id'] = line.order_id.project_id.id
                    new_proc = self.env["procurement.order"].create(vals)
                    new_procs += new_proc
                    to_cancel_procs += line_procs
                continue
            if not line.order_id.procurement_group_id:
                vals = line.order_id._prepare_procurement_group()
                line.order_id.procurement_group_id = self.env["procurement.group"].create(vals)
            vals = line._prepare_order_line_procurement(group_id=line.order_id.procurement_group_id.id)
            vals['product_qty'] = line.product_uom_qty - qty
            vals['account_analytic_id'] = line.order_id.project_id.id
            new_proc = self.env["procurement.order"].create(vals)
            new_procs += new_proc
        to_cancel_procs.cancel()
        new_procs.run()
        return new_procs
