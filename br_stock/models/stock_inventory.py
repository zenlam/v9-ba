from openerp.osv import osv
from openerp.exceptions import UserError
from openerp import models, fields, api, SUPERUSER_ID, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp.addons.stock.stock import stock_inventory_line
import time

from openerp.addons.connector.queue.job import (
    job
)

from openerp.addons.connector.session import (
    ConnectorSession
)


@job
def _post_inventory(session, model_name, inventory_id):
    inventory = session.env[model_name].browse(inventory_id)
    if inventory:
        inventory.post_inventory(inventory)


# Old API ?
class StockInvetory(osv.osv):
    _inherit = 'stock.inventory'

    validate_by = fields.Many2one('res.users', string='Validate by', readonly=True)

    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory
        @return: True
        """
        for inv in self.browse(cr, uid, ids, context=context):
            self.action_check(cr, uid, [inv.id], context=context)
            self.write(cr, uid, [inv.id], {'state': 'done', 'validate_by': uid}, context=context)
            session = ConnectorSession(cr, uid, context=context)
            _post_inventory.delay(session, 'stock.inventory', inv.id)
            # self.post_inventory(cr, uid, inv, context=context)
        return True


class stock_inventory(models.Model):
    _inherit = 'stock.inventory'
    _order = "date desc, id desc"

    INVENTORY_STATE_SELECTION = [
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('waiting', 'Start Inventory'),
        ('confirm', 'In Progress'),
        ('done', 'Validated'),
    ]

    state = fields.Selection(INVENTORY_STATE_SELECTION, 'Status', readonly=True, select=True, copy=False)
    br_loss_inventory_id = fields.Many2one('stock.location', string="Loss Location", compute='_get_loss_inventory_id')
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')], track_visibility='always')
    account_analytic_id_related = fields.Many2one('account.analytic.account', string='Analytic Account', related='account_analytic_id')
    line_ids = fields.One2many(comodel_name='stock.inventory.line', inverse_name='inventory_id', oldname='line_ids', copy=False)

    @api.one
    def _get_loss_inventory_id(self):
        if self.location_id:
            loss_location = self.location_id.get_loss_location()
            if loss_location:
                self.br_loss_inventory_id = loss_location[0].id

    @api.multi
    def action_inventory_line_tree(self):
        action = self.env.ref('br_stock.action_inventory_line_tree').read()[0]
        action['context'] = {
            'default_location_id': self.location_id.id,
            'default_product_id': self.product_id.id,
            'default_prod_lot_id': self.lot_id.id,
            'default_package_id': self.package_id.id,
            'default_partner_id': self.partner_id.id,
            'default_analytic_account': self.account_analytic_id.id,
            'default_loss_location': self.br_loss_inventory_id.id,
            'default_inventory_id': self.id,
        }
        return action

    @api.onchange('location_id')
    def onchange_location_id(self):
        """
        - Get analytic account from outlet if outlet doesn't have analytic account
          then use analytic account from inventory location instead.

        - Get loss location from current location.
        :return:
        """
        if self.location_id:
            des_location = self.location_id
            analytic_account_id = des_location.br_analytic_account_id
            if not analytic_account_id:
                warehouse_id = self.env['stock.location'].get_warehouse(des_location)
                if warehouse_id:
                    outlet = self.env['br_multi_outlet.outlet'].search([('warehouse_id', '=', warehouse_id)])
                    if outlet and outlet.analytic_account_id:
                        analytic_account_id = outlet.analytic_account_id
            loss_location_id = des_location.get_loss_location()
            if loss_location_id:
                self.br_loss_inventory_id = loss_location_id.id
            self.account_analytic_id = analytic_account_id

    @api.onchange('br_loss_inventory_id')
    def onchange_loss_location_id(self):
        if self.br_loss_inventory_id:
            if self.line_ids:
                for line in self.line_ids:
                    line.br_loss_inventory_id = self.br_loss_inventory_id

    @api.onchange('account_analytic_id')
    def onchange_account_analytic_id(self):
        if self.account_analytic_id:
            if self.line_ids:
                for line in self.line_ids:
                    line.account_analytic_id = self.account_analytic_id

    def _get_inventory_lines(self, cr, uid, inventory, context=None):
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        location_ids = location_obj.search(cr, uid, [('id', 'child_of', [inventory.location_id.id])], context=context)
        domain = ' location_id in %s'
        args = (tuple(location_ids),)
        if inventory.company_id.id:
            domain += ' and company_id = %s'
            args += (inventory.company_id.id,)
        if inventory.partner_id:
            domain += ' and owner_id = %s'
            args += (inventory.partner_id.id,)
        if inventory.lot_id:
            domain += ' and lot_id = %s'
            args += (inventory.lot_id.id,)
        if inventory.product_id:
            domain += ' and product_id = %s'
            args += (inventory.product_id.id,)
        if inventory.package_id:
            domain += ' and package_id = %s'
            args += (inventory.package_id.id,)

        cr.execute(self._get_inventory_lines_query(domain, inventory), args)
        vals = []
        inventory_products = []
        for product_line in cr.dictfetchall():
            # replace the None the dictionary by False, because falsy values are tested later on
            for key, value in product_line.items():
                if not value:
                    product_line[key] = False
            product_line['inventory_id'] = inventory.id
            product_line['theoretical_qty'] = product_line['product_qty']
            product_line['is_loaded'] = True
            if product_line['product_id']:
                product = product_obj.browse(cr, uid, product_line['product_id'], context=context)
                product_line['product_uom_id'] = product.uom_id.id
                inventory_products.append(product_line['product_id'])
            vals.append(product_line)
        if inventory.filter == 'none':
            remaining_product_ids = product_obj.search(cr, uid, [('id', 'not in', inventory_products)], context=context)
            remaining_products = product_obj.browse(cr, uid, remaining_product_ids)
            for product in remaining_products:
                line = {
                    'inventory_id': inventory.id,
                    'theoretical_qty': 0,
                    'prod_lot_id': False,
                    'package_id': False,
                    'partner_id': False,
                    'br_supplier_id': False,
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                    'location_id': inventory.location_id.id
                }
                vals.append(line)
        return vals

    def _get_inventory_lines_query(self, domain, inventory):
        return '''
           SELECT
            product_id, sum(qty) as product_qty,
            location_id,
            lot_id as prod_lot_id,
            package_id,
            owner_id as partner_id,
            vendor_id as br_supplier_id
           FROM stock_quant
           WHERE''' + domain + '''
           GROUP BY product_id, location_id, lot_id, package_id, partner_id, vendor_id
        '''

    def prepare_inventory(self, cr, uid, ids, context=None):
        inventory_line_obj = self.pool.get('stock.inventory.line')
        for inventory in self.browse(cr, uid, ids, context=context):
            # If there are inventory lines already (e.g. from import), respect those and set their theoretical qty
            line_ids = [line.id for line in inventory.line_ids]
            if not line_ids and inventory.filter != 'partial':
                # compute the inventory lines and create them
                vals = self._get_inventory_lines(cr, uid, inventory, context=context)

                for product_line in vals:
                    product_line['product_qty'] = 0

                    # load supplier by serial number
                    if product_line['prod_lot_id'] and product_line['product_id']:
                        product = self.pool['product.product'].browse(cr, uid, product_line['product_id'])

                        product_line['br_supplier_id'] = self.pool['stock.production.lot'].browse(cr, uid, product_line[
                            'prod_lot_id']).br_supplier_id.id
                        supplier = self.pool['product.supplierinfo'].search(cr, uid, [
                            ('name', '=', product_line['br_supplier_id'])
                            , ('product_tmpl_id', '=', product.product_tmpl_id.id)],
                                                                            limit=1)
                        if supplier:
                            product_line['product_uom_id'] = product.uom_id.id
                            ls_uoms = self.pool['product.supplierinfo'].browse(cr, uid, supplier).uom_ids
                            for uom in ls_uoms:
                                if uom.level_uom == 'level2':
                                    product_line['br_uom_l2'] = uom.id
                                if uom.level_uom == 'level3':
                                    product_line['br_uom_l3'] = uom.id
                                if uom.level_uom == 'level4':
                                    product_line['br_uom_l4'] = uom.id
                    elif product_line['prod_lot_id'] is False:
                        product = self.pool['product.product'].browse(cr, uid, product_line['product_id'])
                        if product.seller_ids:
                            for u in product.seller_ids[0].uom_ids:
                                uom_id = self.pool.get('product.uom').search(cr, uid, [('name', '=', u.name), (
                                    'category_id', '=', u.category_id.id)], limit=1)
                                if u.level_uom == 'level2' and len(uom_id):
                                    product_line['br_uom_l2'] = uom_id[0]
                                elif u.level_uom == 'level3' and len(uom_id):
                                    product_line['br_uom_l3'] = uom_id[0]
                                elif u.level_uom == 'level4' and len(uom_id):
                                    product_line['br_uom_l4'] = uom_id[0]

                    # load analytic account
                    product_line[
                        'account_analytic_id'] = inventory.account_analytic_id and inventory.account_analytic_id.id or False
                    product_line[
                        'br_loss_inventory_id'] = inventory.br_loss_inventory_id and inventory.br_loss_inventory_id.id or False

                    line_id = inventory_line_obj.create(cr, uid, product_line, context=context)
                    line_record = inventory_line_obj.browse(cr, uid, line_id)
                    is_edit_lot = False
                    if inventory.location_id.manage_expirydate and inventory.manage_expirydate:
                        if not line_record.prod_lot_id and line_record.product_id.tracking in ['serial', 'lot'] \
                                and line_record.theoretical_qty == 0:
                            is_edit_lot = True
                    line_record.is_edit_lot = is_edit_lot
        self.write(cr, uid, ids, {'state': 'waiting', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

    def action_confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'confirm'})


class StockInventoryLine(models.Model):
    _inherit = 'stock.inventory.line'

    prod_lot_id = fields.Many2one(comodel_name='stock.production.lot', string='Expiry date', domain="[('product_id','=',product_id)]", oldname='prod_lot_id')

    @api.multi
    @api.depends('product_id')
    def _compute_vendor_uom_count(self):
        for m in self:
            if m.product_id:
                found = 0
                for vendor in m.product_id.seller_ids:
                    if len(vendor.uom_ids) > 0:
                        found = 1
                        break
                m.vendor_uom_count = found

    @api.depends('product_uom_id')
    @api.multi
    def _get_product_standard_uom(self):
        for l in self:
            l.product_standard_uom = l.product_id.uom_id if l.product_id else None

    br_supplier_id = fields.Many2one('res.partner', string="Supplier")
    br_loss_inventory_id = fields.Many2one('stock.location', string="Loss Location", related='inventory_id.br_loss_inventory_id', readonly=1)

    br_qty_l1 = fields.Float(string="Qty")
    br_qty_l2 = fields.Float(string="Qty")
    br_qty_l3 = fields.Float(string="Qty")
    br_qty_l4 = fields.Float(string="Qty")

    br_uom_l2 = fields.Many2one('product.uom', string="UOM L2")
    br_uom_l3 = fields.Many2one('product.uom', string="UOM L3")
    br_uom_l4 = fields.Many2one('product.uom', string="UOM L4")

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')], track_visibility='always')
    product_standard_uom = fields.Many2one('product.uom', compute='_get_product_standard_uom')
    vendor_uom_count = fields.Integer(_('Uom qty from vendor'), compute='_compute_vendor_uom_count')
    is_loaded = fields.Boolean(_("Is Loaded By Default"), default=False)
    remark = fields.Text(string=_("Remark"))
    inventory_location_id = fields.Many2one(
        'stock.location', 'Location', related='inventory_id.location_id', related_sudo=False)
    is_edit_lot = fields.Boolean(default=False)

    def _get_quants(self, cr, uid, line, context=None):
        dom = self._get_quant_dom(line)
        quant_obj = self.pool.get("stock.quant")
        quants = quant_obj.search(cr, uid, dom, context=context)
        return quants

    def _get_quant_dom(self, line):
        dom = [('company_id', '=', line.company_id.id),
               ('location_id', '=', line.location_id.id),
               ('lot_id', '=', line.prod_lot_id.id),
               ('product_id', '=', line.product_id.id),
               ('owner_id', '=', line.partner_id.id),
               ('package_id', '=', line.package_id.id),
               ('vendor_id', '=', line.br_supplier_id.id if line.br_supplier_id else None)]
        return dom

    @api.multi
    @api.onchange('br_supplier_id', 'product_id')
    def onchange_br_supplier_id(self):
        for l in self:
            if l.product_id:
                seller = l.product_id._select_seller(l.product_id, partner_id=l.br_supplier_id or None)
                if seller:
                    uoms = {}
                    for u in seller.uom_ids:
                        uoms[u.level_uom] = u.id
                    l.br_uom_l2 = uoms.get('level2', None)
                    l.br_uom_l3 = uoms.get('level3', None)
                    l.br_uom_l4 = uoms.get('level4', None)

    def create(self, cr, uid, values, context=None):
        if not context.get('lines_checked', False):
            product_obj = self.pool.get('product.product')
            dom = [('product_id', '=', values.get('product_id')), ('inventory_id.state', '=', 'waiting'),
                   ('location_id', '=', values.get('location_id')), ('partner_id', '=', values.get('partner_id')),
                   ('package_id', '=', values.get('package_id')), ('prod_lot_id', '=', values.get('prod_lot_id')),
                   ('br_supplier_id', '=', values.get('br_supplier_id'))]
            res = self.search(cr, uid, dom, context=context)
            if res:
                location = self.pool['stock.location'].browse(cr, uid, values.get('location_id'), context=context)
                product = product_obj.browse(cr, uid, values.get('product_id'), context=context)
                raise UserError(_(
                    "You cannot have two inventory adjustements in state 'in Progess' with the same product(%s), same location(%s), same package, same owner and same lot. Please first validate the first inventory adjustement with this product before creating another one.") % (
                                    product.name, location.name))
        if 'product_id' in values and not 'product_uom_id' in values:
            values['product_uom_id'] = product_obj.browse(cr, uid, values.get('product_id'), context=context).uom_id.id
        return super(stock_inventory_line, self).create(cr, uid, values, context=context)

    @api.model
    def default_get(self, fields):
        rec = super(StockInventoryLine, self).default_get(fields)
        context = self._context
        # default analytic account id
        if 'default_analytic_account' in context and context['default_analytic_account']:
            rec['account_analytic_id'] = context['default_analytic_account']

        # default loss location id
        if 'default_loss_location' in context and context['default_loss_location']:
            rec['br_loss_inventory_id'] = context['default_loss_location']
        return rec

    @api.onchange('product_uom_id', 'br_qty_l1', 'br_qty_l2', 'br_qty_l3', 'br_qty_l4', 'br_uom_l2', 'br_uom_l3',
                  'br_uom_l4')
    def onchange_uom(self):
        uom_obj = self.env["product.uom"]
        prod_qty = 0
        if self.product_uom_id and self.br_qty_l1:
            prod_qty += uom_obj._compute_qty(self.product_uom_id.id, self.br_qty_l1, self.product_id.uom_id.id)
        if self.br_uom_l2 and self.br_qty_l2:
            prod_qty += uom_obj._compute_qty(self.br_uom_l2.id, self.br_qty_l2, self.product_id.uom_id.id)
        if self.br_uom_l3 and self.br_qty_l3:
            prod_qty += uom_obj._compute_qty(self.br_uom_l3.id, self.br_qty_l3, self.product_id.uom_id.id)
        if self.br_uom_l4 and self.br_qty_l4:
            prod_qty += uom_obj._compute_qty(self.br_uom_l4.id, self.br_qty_l4, self.product_id.uom_id.id)
        self.product_qty = prod_qty

    @api.onchange('prod_lot_id')
    def onchange_prod_lot_id(self):
        if self.prod_lot_id and self.product_id:
            self.br_supplier_id = self.prod_lot_id.br_supplier_id
            self._set_uom()
        else:
            self.br_supplier_id = None

    def _set_uom(self):
        dom = [('name', '=', self.br_supplier_id.id),
               ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id)]
        supplier = self.env['product.supplierinfo'].search(dom, limit=1)
        if supplier:
            for item in supplier.uom_ids:
                if item.level_uom == 'level2':
                    self.br_uom_l2 = item
                if item.level_uom == 'level3':
                    self.br_uom_l3 = item
                if item.level_uom == 'level4':
                    self.br_uom_l4 = item
                self.product_uom_id = supplier.product_tmpl_id.uom_id

    @api.depends('br_supplier_id', 'product_id')
    def onchange_createline(self, cr, uid, ids, location_id=False, product_id=False, uom_id=False, package_id=False,
                            prod_lot_id=False, partner_id=False, company_id=False, context=None):
        result = super(StockInventoryLine, self).onchange_createline(cr, uid, ids, location_id=location_id,
                                                                     uom_id=uom_id, package_id=package_id,
                                                                     prod_lot_id=prod_lot_id, partner_id=package_id,
                                                                     company_id=company_id, context=context)
        result.setdefault('value', {})
        result['value']['is_edit_lot'] = False
        if product_id:
            product = self.pool['product.product'].browse(cr, uid, product_id, context=context)
            uom = self.pool['product.uom'].browse(cr, uid, uom_id, context=context)
            if product.uom_id.category_id.id != uom.category_id.id:
                result['value']['product_uom_id'] = product.uom_id.id
            if len(product.seller_ids) == 1:
                vendor = product._select_seller(product)
                result['value']['br_supplier_id'] = vendor.name.id
            else:
                result['value']['br_supplier_id'] = None

            # check manage_expiry date of product to required lot
            manage_expirydate = context.get('manage_expirydate', False)  # get from parent - stock.inventory
            parent_location_id = context.get('parent_location_id', False)  # get from parent - stock.inventory
            if parent_location_id:
                localtion = self.pool['stock.location'].browse(cr, uid, parent_location_id)
                if manage_expirydate and localtion.manage_expirydate and product.tracking in ('serial', 'lot'):
                    result['value']['is_edit_lot'] = True
        else:
            result['value']['br_supplier_id'] = None
        return result

    def get_stock_move_vals(self, cr, uid, inventory_line, context=None):
        return {
            'name': _('INV:') + (inventory_line.inventory_id.name or ''),
            'product_id': inventory_line.product_id.id,
            'product_uom': inventory_line.product_id.uom_id.id,
            'date': inventory_line.inventory_id.date,
            'company_id': inventory_line.inventory_id.company_id.id,
            'inventory_id': inventory_line.inventory_id.id,
            'state': 'confirmed',
            'restrict_lot_id': inventory_line.prod_lot_id.id,
            'restrict_partner_id': inventory_line.partner_id.id,
            'account_analytic_id': inventory_line.account_analytic_id.id,
            'inventory_line_id': inventory_line.id,
        }

    def _resolve_inventory_line(self, cr, uid, inventory_line, context=None):
        stock_move_obj = self.pool.get('stock.move')
        quant_obj = self.pool.get('stock.quant')
        diff = inventory_line.theoretical_qty - inventory_line.product_qty
        if not diff:
            return
        # each theorical_lines where difference between theoretical and checked quantities is not 0 is a line for which we need to create a stock move
        vals = self.get_stock_move_vals(cr, uid, inventory_line, context=context)
        inventory_location_id = inventory_line.br_loss_inventory_id.id or inventory_line.product_id.property_stock_inventory.id
        if diff < 0:
            # found more than expected
            vals['location_id'] = inventory_location_id
            vals['location_dest_id'] = inventory_line.location_id.id
            vals['product_uom_qty'] = -diff
        else:
            # found less than expected
            vals['location_id'] = inventory_line.location_id.id
            vals['location_dest_id'] = inventory_location_id
            vals['product_uom_qty'] = diff
        move_id = stock_move_obj.create(cr, uid, vals, context=context)
        move = stock_move_obj.browse(cr, uid, move_id, context=context)
        if diff > 0:
            domain = [('qty', '>', 0.0), ('package_id', '=', inventory_line.package_id.id),
                      ('lot_id', '=', inventory_line.prod_lot_id.id),
                      ('location_id', '=', inventory_line.location_id.id)]
            preferred_domain_list = [[('reservation_id', '=', False)],
                                     [('reservation_id.inventory_id', '!=', inventory_line.inventory_id.id)]]
            quants = quant_obj.quants_get_preferred_domain(cr, uid, move.product_qty, move, domain=domain,
                                                           preferred_domain_list=preferred_domain_list)
            quant_obj.quants_reserve(cr, uid, quants, move, context=context)
        elif inventory_line.package_id:
            stock_move_obj.action_done(cr, uid, move_id, context=context)
            quants = [x.id for x in move.quant_ids]
            quant_obj.write(cr, uid, quants, {'package_id': inventory_line.package_id.id}, context=context)
            res = quant_obj.search(cr, uid, [('qty', '<', 0.0), ('product_id', '=', move.product_id.id),
                                             ('location_id', '=', move.location_dest_id.id),
                                             ('package_id', '!=', False)], limit=1, context=context)
            if res:
                for quant in move.quant_ids:
                    if quant.location_id.id == move.location_dest_id.id:  # To avoid we take a quant that was reconcile already
                        quant_obj._quant_reconcile_negative(cr, uid, quant, move, context=context)
        return move_id