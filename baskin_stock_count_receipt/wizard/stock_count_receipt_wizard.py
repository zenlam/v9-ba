# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
import itertools
from openerp.exceptions import UserError
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import time
import openerp.addons.decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)

class TemplateGroupName(models.Model):
    _name = 'template.group.name'
    
    name = fields.Char("Group")
    

class StockInventoryLineToPrint(models.Model):
    _name = 'stock.inventory.line.to.print'
    _order = 'is_total_count DESC, group_name, product_name, br_supplier_id, prod_lot_id'
    
    @api.depends('product_uom_id')
    @api.multi
    def _get_product_standard_uom(self):
        for l in self:
            l.product_standard_uom = l.product_id.uom_id if l.product_id else None
            
    inventory_id = fields.Many2one('stock.inventory', 'Inventory')
    location_id = fields.Many2one('stock.location', 'Location')
    product_id = fields.Many2one('product.product', 'Product')
    package_id = fields.Many2one('stock.quant.package', 'Pack')
    product_uom_id = fields.Many2one('product.uom', 'Product Unit of Measure')
    product_qty = fields.Float('Checked Quantity', digits_compute=dp.get_precision('Product Unit of Measure'))
    company_id = fields.Many2one(related='inventory_id.company_id', string='Company', store=True)
    prod_lot_id = fields.Many2one('stock.production.lot', 'Serial Number', domain="[('product_id','=',product_id)]")
    state = fields.Selection(related='inventory_id.state', string='Status', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Owner')
    product_code = fields.Char(related='product_id.default_code', string='Product Code', store=True)
    location_name = fields.Char(related='location_id.complete_name', string='Location Name', store=True)
    prodlot_name = fields.Char(related='prod_lot_id.name', string='Serial Number Name', store=True)
    product_name = fields.Char(related="product_id.name", store=True, string="Product Name")
    theoretical_qty = fields.Float('theoretical_qty')
    
    br_supplier_id = fields.Many2one('res.partner', string="Supplier")
    br_loss_inventory_id = fields.Many2one('stock.location', string="Loss Location")

    br_qty_l1 = fields.Float(string="Qty")
    br_qty_l2 = fields.Float(string="Qty")
    br_qty_l3 = fields.Float(string="Qty")
    br_qty_l4 = fields.Float(string="Qty")

    br_uom_l2 = fields.Many2one('product.uom', string="UOM L2")
    br_uom_l3 = fields.Many2one('product.uom', string="UOM L3")
    br_uom_l4 = fields.Many2one('product.uom', string="UOM L4")

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', ondelete='set null',
                                          domain=[('account_type', '=', 'normal')])

    product_standard_uom = fields.Many2one('product.uom', compute='_get_product_standard_uom')
    vendor_uom_count = fields.Integer(_('Uom qty from vendor'), compute='_compute_vendor_uom_count')
    is_loaded = fields.Boolean(_("Is Loaded By Default"), default=False)
    remark = fields.Text(string=_("Remark"))
    inventory_location_id = fields.Many2one(
        'stock.location', 'Location', related='inventory_id.location_id', related_sudo=False)
    
    template_line_id = fields.Many2one(comodel_name='stock.inventory.template.line', string="Template Line")
    group_name = fields.Char(string="Template Group Name")
    group_type = fields.Selection(string="Template Group Type",
                                  related='template_line_id.group_type')
    is_total_count = fields.Boolean(related='template_line_id.is_total_count', store=True)
    
    stock_count_receipt_wizard_id = fields.Many2one('stock.count.receipt.wizard', string="print receipt wizard")
    
    
    
    
class stock_count_receipt_wizard(models.Model):
    _name = 'stock.count.receipt.wizard'
    
    inventory_id = fields.Many2one('stock.inventory', string="Inventory")
    inventory_line_print_ids = fields.One2many('stock.inventory.line.to.print','stock_count_receipt_wizard_id', string="print lines")
    group_name_ids_string = fields.Char('group_name_ids')
    group_name_ids = fields.Many2many('template.group.name', string="Selected Groups")
    all_group = fields.Boolean('All Group')
    
    @api.onchange('group_name_ids_string')
    def onchange_group_name_ids_string(self):
        vals = {}
        if self.group_name_ids_string:
            vals = {'domain':
                        {'group_name_ids':[('id','in',[ int(x) for x in self.group_name_ids_string.split(',')])]}
                    }
        return vals
    
    @api.model
    def default_get(self, fields):
        rec = super(stock_count_receipt_wizard, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')

        # Checks on context parameters
        if not active_model or not active_ids:
            raise UserError(_("Programmation error: wizard action executed without active_model or active_ids in context."))
        if active_model != 'stock.inventory':
            raise UserError(_("Programmation error: the expected model for this action is 'stock.inventory'. The provided one is '%d'.") % active_model)
        if active_ids and len(active_ids) > 1:
            raise UserError(_("Multiple inventory receipt is not supported !"))
        
        # Checks on received invoice records
        inventory = self.env[active_model].browse(active_ids)
        
        group_ids = []
        if inventory:
            group_ids.append(self.env['template.group.name'].create({'name':'Others'}).id)
            for template_line in inventory.template_id.line_ids:
                group_ids.append(self.env['template.group.name'].create({'name':template_line.group_name}).id)
                
        
        rec.update({
            'inventory_id': inventory.id,
            'group_name_ids_string': ','.join(str(x) for x in group_ids)
        })
        return rec
    
    @api.multi
    def action_print(self):
        # delete lines first if exist       
        self.env['stock.inventory.line.to.print'].search([('stock_count_receipt_wizard_id','=',self.id)]).unlink()
        
        new_ctx = self.env.context.copy()
        new_ctx.update(lines_checked=True)
        inventory = self.with_context(new_ctx).inventory_id
        if inventory.state == 'draft':
            line_obj = self.with_context(new_ctx).env['stock.inventory.line.to.print']
            if inventory.filter == 'none':
                if inventory.stock_count_type == 'official':
                    # If stock count is official, do normal inventory adjustment
                    inventory.with_context(ignore_for_reciept_printing=True).wizard_prepare_inventory(self)
                elif inventory.stock_count_type == 'unofficial':
                    for inventory_lines in self.env['stock.inventory']._get_inventory_lines(inventory):
                        if inventory_lines['group_name'] in [x.name for x in self.group_name_ids] or self.all_group:
                            inventory_lines.update(product_qty=0)
                            inventory_lines.update(stock_count_receipt_wizard_id = self.id)
                            line_obj.create(inventory_lines)
            elif inventory.filter == 'partial':
                template_inventory_lines = inventory._wizard_get_template_inventory_lines()
                for inventory_lines in template_inventory_lines:
                    if inventory_lines['group_name'] in [x.name for x in self.group_name_ids] or self.all_group:
                        inventory_lines.update(stock_count_receipt_wizard_id = self.id)
                        line_obj.create(inventory_lines)
                    
            return self.env['report'].get_action(self, 'baskin_stock_count_receipt.pre_stock_count_report')
        else:
            return self.env['report'].get_action(self, 'baskin_stock_count_receipt.report_stock_count')
                
    @api.model
    def erase_stock_count_model_data(self):
        self.env['stock.count.receipt.wizard'].search([]).unlink()
        self.env['stock.inventory.line.to.print'].search([]).unlink()
        self.env['template.group.name'].search([]).unlink()
                    
class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    def wizard_prepare_inventory(self, cr, uid, ids, receipt_wizard, context=None):

        inventory_line_obj = self.pool.get('stock.inventory.line.to.print')
        for inventory in self.browse(cr, uid, ids, context=context):
            # If there are inventory lines already (e.g. from import), respect those and set their theoretical qty
#             line_ids = [line.id for line in inventory.line_ids]
            if inventory.filter != 'partial':
                # compute the inventory lines and create them
                
                vals = self._get_inventory_lines(cr, uid, inventory, context=context)
                
                for product_line in vals:
                    if product_line['group_name'] in [x.name for x in receipt_wizard.group_name_ids] or receipt_wizard.all_group:
                        product_line['stock_count_receipt_wizard_id'] = receipt_wizard.id
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
                        
                        
                        inventory_line_obj.create(cr, uid, product_line, context=context)



    @api.multi
    def _wizard_get_template_inventory_lines(self, unofficial_line=None):
        self.ensure_one()
        vals = []
        product_obj = self.env['product.product']
        template_products = {}
        inventory_products = []
        if unofficial_line and unofficial_line.template_line_id:
            for product in unofficial_line.template_line_id.all_product_ids:
                template_products[product.id] = unofficial_line.template_line_id
        else:
            for line in self.template_id.line_ids:
                for product in line.all_product_ids:
                    template_products[product.id] = line
        if template_products:
            domain = ' product_id in %s'
            args = (tuple(template_products),)
            if self.location_id:
                location_obj = self.env['stock.location']
                location_ids = location_obj.search([('id', 'child_of', [self.location_id.id])])
                domain += ' and location_id in %s'
                args += (tuple(location_ids.ids),)
            if self.company_id:
                domain += ' and company_id = %s'
                args += (self.company_id.id,)
            self.env.cr.execute(self._get_inventory_lines_query(domain, self), args)
            lines_data = self.env.cr.dictfetchall()
            group_items = {}
            stock_count_type = self.stock_count_type
            for product_line in lines_data:
                # replace the None the dictionary by False, because falsy values are tested later on
                for key, value in product_line.items():
                    if not value:
                        product_line[key] = False
                temp_line = template_products[product_line['product_id']]
                product_line['is_loaded'] = True
                product_line['group_name'] = temp_line.group_name
                product_line['template_line_id'] = temp_line.id
                product_line['inventory_id'] = self.id
                product_line.update(product_qty=0)
                if product_line['product_id']:
                    product = self.env['product.product'].browse(product_line['product_id'])
                    product_line['product_uom_id'] = product.uom_id.id
                    inventory_products.append(product.id)
                # Group product_line by group name
                if not temp_line.is_total_count or stock_count_type == 'official':
                    inv_product = product_obj.browse(product_line['product_id'])
                    if 'br_supplier_id' in product_line and product_line['br_supplier_id']:
                        supplier = inv_product.product_tmpl_id.seller_ids.filtered(lambda x: x.name.id == product_line['br_supplier_id'])
                        supplier = supplier[0] if supplier else False
                    else:
                        supplier = self.get_product_supplier(inv_product)
                    self.set_uom_level(product_line, supplier)
                    vals.append(product_line)
                else:
                    if temp_line.group_name not in group_items:
                        ref_product = temp_line.ref_product_id
                        if ref_product:
                            supplier = self.get_product_supplier(ref_product)
                            self.set_uom_level(product_line, supplier)
                            product_line.update(
                                product_id=ref_product.id,
                                br_supplier_id=supplier.name.id if supplier else False,
                                product_uom_id=ref_product.uom_id.id,
                                partner_id=False,
                                prod_lot_id=False,
                            )
                        group_items[temp_line.group_name] = product_line
            # Products that can't be found in location but configured on template
            remaining_products = self.env['product.product'].browse(
                [x for x in template_products if x not in inventory_products])
            for product in remaining_products:
                temp_line = template_products[product.id]
                # If inventory line is total count or this is official inventory then don't need to fill in product info
                if not temp_line.is_total_count or stock_count_type == 'official':
                    supplier = self.get_product_supplier(product)
                    product_line = {
                        'is_loaded': True,
                        'group_name': temp_line.group_name,
                        'template_line_id': temp_line.id,
                        'inventory_id': self.id,
                        'theoretical_qty': 0,
                        'prod_lot_id': False,
                        'package_id': False,
                        'partner_id': False,
                        'br_supplier_id': supplier.name.id if supplier else False,
                        'product_id': product.id,
                        'product_uom_id': product.uom_id.id,
                        'location_id': self.location_id.id
                    }
                    self.set_uom_level(product_line, supplier)
                    vals.append(product_line)
                else:
                    if temp_line.group_name not in group_items:
                        group_items[temp_line.group_name] = {
                            # 'is_loaded': True,
                            'group_name': temp_line.group_name,
                            'template_line_id': temp_line.id,
                            'inventory_id': self.id,
                            'theoretical_qty': 0,
                            'prod_lot_id': False,
                            'package_id': False,
                            'partner_id': False,
                            'location_id': self.location_id.id,
                        }
                        ref_product = temp_line.ref_product_id
                        if ref_product:
                            supplier = self.get_product_supplier(ref_product)
                            self.set_uom_level(group_items[temp_line.group_name], supplier)
                            group_items[temp_line.group_name].update(
                                product_id=ref_product.id,
                                br_supplier_id=supplier.name.id if supplier else False,
                                product_uom_id=ref_product.uom_id.id,
                                partner_id=False,
                                prod_lot_id=False,
                            )
            vals.extend([group_items[x] for x in group_items])

        self.with_context(ignore_for_reciept_printing=True).check_valid_inventory_lines(vals)
        return vals
    
    @api.model
    def check_valid_inventory_lines(self, lines):
        if self._context.get('ignore_for_reciept_printing'):
            return True
        return super(StockInventory, self).check_valid_inventory_lines(lines)
    
