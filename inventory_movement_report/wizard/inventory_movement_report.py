import time
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError
import pytz


from openerp import api, fields, models, exceptions, _
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from collections import OrderedDict
import xlsxwriter

import logging
_logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def convert_timezone(from_tz, to_tz, dt):
    from_tz = pytz.timezone(from_tz).localize(datetime.strptime(dt, DATETIME_FORMAT))
    to_tz = from_tz.astimezone(pytz.timezone(to_tz))
    return to_tz.strftime(DATETIME_FORMAT)


class InventoryMovementReport(models.TransientModel):
    _name = 'inventory.movement.report'
    
    location_type = fields.Selection([('fixed','Fixed'),('specific','Specific')], "Location Type", required=True)
    movement_type = fields.Selection([('incoming','Incoming'),('outgoing','Outgoing')], "Movement Type", required=True)
    report_breakdown = fields.Selection([('by_period','By Period'),('by_location','By Location')], 
                                        string="Report Breakdown",
                                        default = 'by_period',
                                        required=True)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    product_categ_ids = fields.Many2many(string='Product Category', comodel_name='product.category')
    product_ids = fields.Many2many(string='Product', comodel_name='product.template')
    warehouse_ids = fields.Many2many(string="Warehouse", relation='movement_fixed_wh_rel', column1='report_id', column2='warehouse_id', comodel_name='stock.warehouse')
    location_ids = fields.Many2many(string="Location", relation='movement_fixed_location_rel', column1='report_id', column2='location_id', comodel_name='stock.location')
    #location must be filtered only stock flag true.
    display_expiry_date = fields.Selection([('yes','Yes'),('no','No')], string="Display Expiry Date", default='no')
    group_product_categ = fields.Selection([('yes','Yes'),('no','No')], string="Group By Product Category", default='no')
    period = fields.Selection([('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly')],string="Group By Date", default='daily')
    uom_type = fields.Selection([('standard', 'Standard'),('distribution', 'Distribution'), ('storage', 'Storage'), ('purchase', 'Purchase')], default='distribution',required=True)
    
    out_source_warehouse_id = fields.Many2one(string="Source Warehouse", relation='movement_specific_out_source_wh_rel', column1='report_id', column2='warehouse_id', comodel_name='stock.warehouse')
    out_source_location_ids = fields.Many2many(string="Source Location", relation='movement_specific_output_source_location_rel', column1='report_id', column2='location_id', comodel_name='stock.location')
    out_destination_warehouse_ids = fields.Many2many(string="Destination Warehouse", relation='movement_specific_wh_out_dest_rel', column1='report_id', column2='warehouse_id', comodel_name='stock.warehouse')
    out_destination_location_ids = fields.Many2many(string="Destination Location", relation='movement_specific_output_dest_location_rel', column1='report_id', column2='location_id', comodel_name='stock.location')
    
    in_source_warehouse_ids = fields.Many2many(string="Source Warehouse", relation='movement_specific_wh_in_source_rel', column1='report_id', column2='warehouse_id', comodel_name='stock.warehouse')
    in_source_location_ids = fields.Many2many(string="Source Location", relation='movement_specific_source_input_location_rel', column1='report_id', column2='location_id', comodel_name='stock.location')
    in_destination_warehouse_id = fields.Many2one(string="Destination Warehouse", relation='movement_specific_wh_in_dest_rel', column1='report_id', column2='warehouse_id', comodel_name='stock.warehouse')
    in_destination_location_ids = fields.Many2many(string="Destination Location", relation='movement_specific_dest_input_location_rel', column1='report_id', column2='location_id', comodel_name='stock.location')
    
    base_on_date = fields.Selection([('move_date','Stock Picking Date of Transfer'),('expected_date','Stock Picking Schedule Date')], default='move_date', required=True, string="Based on")

    hq_wh = fields.Boolean("HQ Warehouses")
    outlet_wh = fields.Boolean("Outlet Warehouses")
    from_hq_wh = fields.Boolean("From HQ Warehouses")
    from_outlet_wh = fields.Boolean("From Outlet Warehouses")
    to_hq_wh = fields.Boolean("TO HQ Warehouses")
    to_outlet_wh = fields.Boolean("To Outlet Warehouses")

    type_stockable = fields.Boolean('Stockable', default=True)
    type_consumable = fields.Boolean('Consumbale')
    type_service = fields.Boolean('Service')

    @api.one
    @api.constrains('start_date', 'end_date')
    def end_date_greater_then_start(self):
        if self.start_date and self.end_date and datetime.strptime(self.start_date,DEFAULT_SERVER_DATE_FORMAT) > datetime.strptime(self.end_date,DEFAULT_SERVER_DATE_FORMAT):
            raise exceptions.ValidationError(_('Start date must be smaller then end date !'))
    
    @api.onchange('report_breakdown','start_date')
    def onchange_report_breakdown(self):
        if self.report_breakdown and self.report_breakdown == 'by_location' and self.start_date:
            self.end_date = self.start_date
    
    @api.onchange('product_categ_ids','type_stockable','type_consumable','type_service')
    def onchange_product_categ_ids(self):
        product_domain = []



        if self.type_stockable:
            if product_domain :
                product_domain.insert(0,'|')
                product_domain += [('type', '=', 'product')]
            else:
                product_domain += [('type', '=', 'product')]

        if self.type_consumable:
            if product_domain:
                product_domain.insert(0, '|')
                product_domain += [('type', '=', 'consu')]
            else:
                product_domain += [('type', '=', 'consu')]

        if self.type_service:
            if product_domain:
                product_domain.insert(0, '|')
                product_domain += [('type', '=', 'service')]
            else:
                product_domain += [('type', '=', 'service')]

        if self.product_categ_ids:
            if product_domain :
                product_domain.insert(0, ('categ_id', 'child_of', [x.id for x in self.product_categ_ids]) )
                product_domain.insert(0,'&')
            else:
                product_domain += [('categ_id', 'child_of', [x.id for x in self.product_categ_ids])]
        return {'domain': {'product_ids': product_domain}}
    
    @api.onchange('warehouse_ids')
    def onchange_warehouse_ids(self):
        res = {'domain': {'location_ids':[('usage', '!=', 'view')]}}
        if self.warehouse_ids:
            view_loc = [x.view_location_id.id for x in self.warehouse_ids]
            res = {'domain': {'location_ids': [('id', 'child_of', view_loc)]}}
        return res
    
    @api.onchange('out_source_warehouse_id')
    def onchange_out_source_warehouse_id(self):
        res = {'domain': {'out_source_location_ids':[('usage', '!=', 'view')]}}
        if self.out_source_warehouse_id:
            view_loc = [self.out_source_warehouse_id.view_location_id.id]
            res = {'domain': {'out_source_location_ids': [('id', 'child_of', view_loc)],
                              'out_destination_warehouse_ids': [('id','!=',self.out_source_warehouse_id.id)] }}
        return res
    
    @api.onchange('out_destination_warehouse_ids')
    def onchange_out_destination_warehouse_ids(self):
        res = {'domain': {'out_destination_location_ids':[('usage', '!=', 'view')]}}
        if self.out_destination_warehouse_ids:
            view_loc = [x.view_location_id.id for x in self.out_destination_warehouse_ids]
            res = {'domain': {'out_destination_location_ids': [('id', 'child_of', view_loc)]}}
        return res
    
    @api.onchange('in_source_warehouse_ids')
    def onchange_in_source_warehouse_ids(self):
        res = {'domain': {'in_source_location_ids':[('usage', '!=', 'view')]}}
        if self.in_source_warehouse_ids:
            view_loc = [x.view_location_id.id for x in self.in_source_warehouse_ids]
            res = {'domain': {'in_source_location_ids': [('id', 'child_of', view_loc)],
                              'in_destination_warehouse_id': [('id','not in',[x.id for x in self.in_source_warehouse_ids])]}}
        return res
    
    @api.onchange('in_destination_warehouse_id')
    def onchange_in_destination_warehouse_id(self):
        res = {'domain': {'in_destination_location_ids':[('usage', '!=', 'view')]}}
        if self.in_destination_warehouse_id:
            view_loc = [self.in_destination_warehouse_id.view_location_id.id]
            res = {'domain': {'in_destination_location_ids': [('id', 'child_of', view_loc)]}}
        return res

    @api.onchange('hq_wh','outlet_wh')
    def onchange_hq_wh_and_outlet_wh(self):
        res = {'domain': {'warehouse_ids': [], 'location_ids': [] }}
        if self.hq_wh and not self.outlet_wh:
            res['domain']['warehouse_ids'] = [('is_main_warehouse','=',True)]
        elif not self.hq_wh and self.outlet_wh:
            res['domain']['warehouse_ids'] = [('is_main_warehouse', '=', False)]
        return res

    @api.onchange('from_hq_wh', 'from_outlet_wh')
    def onchange_from_hq_wh_and_from_outlet_wh(self):
        res = {'domain': {'out_source_warehouse_id': [],
                          'in_source_warehouse_ids': []}}
        if self.from_hq_wh and not self.from_outlet_wh:
            res['domain']['out_source_warehouse_id'] = [('is_main_warehouse', '=', True)]
            res['domain']['in_source_warehouse_ids'] = [('is_main_warehouse', '=', True)]
        elif not self.from_hq_wh and self.from_outlet_wh:
            res['domain']['out_source_warehouse_id'] = [('is_main_warehouse', '=', False)]
            res['domain']['in_source_warehouse_ids'] = [('is_main_warehouse', '=', False)]
        return res

    @api.onchange('to_hq_wh', 'to_outlet_wh')
    def onchange_to_hq_wh_and_to_outlet_wh(self):
        res = {'domain': {'out_destination_warehouse_ids': [],
                          'in_destination_warehouse_ids': []}}
        if self.to_hq_wh and not self.to_outlet_wh:
            res['domain']['out_destination_warehouse_ids'] = [('is_main_warehouse', '=', True)]
            res['domain']['in_destination_warehouse_id'] = [('is_main_warehouse', '=', True)]
        elif not self.to_hq_wh and self.to_outlet_wh:
            res['domain']['out_destination_warehouse_ids'] = [('is_main_warehouse', '=', False)]
            res['domain']['in_destination_warehouse_id'] = [('is_main_warehouse', '=', False)]
        return res

    @api.multi
    def action_print(self):
        # perform flush date checking before printing the report
        self.check_flush_date()
        return self.env['report'].get_action(self, 'inventory_movement_report.stock_inventory_movement_report')

    @api.multi
    def check_flush_date(self):
        """
        Make sure the start date of the report is greater than latest flush
        date
        """
        for res in self:
            # get the latest flush date
            latest_flush_date = self.env['stock.flush.date'].search(
                [], order='flush_date desc', limit=1)
            # check the report start date
            # no need to check for the end date since the end_date must be
            # greater than start_date validation is there.
            if latest_flush_date:
                flush_date = convert_timezone(
                    'UTC',
                    self.env.user.tz or 'UTC',
                    latest_flush_date.flush_date).split(' ')[0]
                if res.start_date and \
                        datetime.strptime(res.start_date,
                                          DEFAULT_SERVER_DATE_FORMAT) < \
                        datetime.strptime(flush_date,
                                          DEFAULT_SERVER_DATE_FORMAT):
                    raise UserError(('Kindly select a start date greater '
                                     'than the flush date.\n Flush Date: '
                                     '%s') % flush_date)
            return True

class stock_inventory_movement_report(ReportXlsx):
    _name = 'report.inventory_movement_report.stock_inventory_movement_report'

    def generate_xlsx_report(self, wb, data, report):
        ws = wb.add_worksheet('Stock Movement')
        self.set_paper(wb, ws)
        self.styles = self.get_report_styles(wb)
        self.set_header(ws, report)
        domain = self.get_domain(report)
        report_data = self.get_data(domain, report)
        self.bind_data(ws, report_data, report)

    def set_paper(self, wb, ws):
        # SET PAPERS
        wb.formats[0].font_name = 'Times New Roman'
        wb.formats[0].font_size = 11
        ws.set_paper(9)
        ws.center_horizontally()
        ws.set_margins(left=0.28, right=0.28, top=0.5, bottom=0.5)
        ws.fit_to_pages(1, 0)
        ws.set_landscape()
        ws.fit_to_pages(1, 1)
 
    def set_header(self, ws, report):
        
        ws.write('A1', 'Movement', self.styles['bold'])
        ws.write('B1', report.movement_type.title())
        
        ws.write('A2', 'Location Type', self.styles['bold'])
        ws.write('B2', report.location_type.title())
        
        ws.write('A3', 'Start Date', self.styles['bold'])
        ws.write_datetime('B3', datetime.strptime(report.start_date, DATE_FORMAT), self.styles['date_left'])
        ws.write('A4', 'End Date', self.styles['bold'])
        ws.write_datetime('B4', datetime.strptime(report.end_date, DATE_FORMAT), self.styles['date_left'])
        
        if report.location_type == 'fixed':
            ws.write('A5', 'Warehouse(s)', self.styles['bold'])
            ws.write('B5', ', '.join([w.name for w in report.warehouse_ids]))
            ws.write('A6', 'Location(s)', self.styles['bold'])
            ws.write('B6', ', '.join([l.complete_name for l in self.get_locations(report)]))
        
        if report.location_type == 'specific':
            source_location, destination_location = self.get_specific_locations(report)
            if report.movement_type == 'incoming':
                ws.write('A5', 'Source Warehouse(s)', self.styles['bold'])
                ws.write('B5', ', '.join([w.name for w in report.in_source_warehouse_ids]))
                ws.write('A6', 'Source Location(s)', self.styles['bold'])
                ws.write('B6', ', '.join([l.complete_name for l in source_location]))
                
                ws.write('A7', 'Destination Warehouse', self.styles['bold'])
                ws.write('B7', report.in_destination_warehouse_id.name )
                ws.write('A8', 'Destination Location(s)', self.styles['bold'])
                ws.write('B8', ', '.join([l.complete_name for l in destination_location]))
            if report.movement_type == 'outgoing':
                ws.write('A5', 'Source Warehouse', self.styles['bold'])
                ws.write('B5', report.out_source_warehouse_id.name )
                ws.write('A6', 'Source Location(s)', self.styles['bold'])
                ws.write('B6', ', '.join([l.complete_name for l in source_location]))
                
                ws.write('A7', 'Destination Warehouse(s)', self.styles['bold'])
                ws.write('B7', ', '.join([w.name for w in report.out_destination_warehouse_ids]) )
                ws.write('A8', 'Destination Location(s)', self.styles['bold'])
                ws.write('B8', ', '.join([l.complete_name for l in destination_location]))
            
        
        ws.write('A9', 'Date Group By', self.styles['bold'])
        ws.write('B9', report.period)
        
        ws.write('A10', 'UOM', self.styles['bold'])
        ws.write('B10', report.uom_type)

        if not report.product_ids:
            self.get_product(report)

        product_type_name = self.get_product_type_name(report)

        ws.write('A11', 'Product Type', self.styles['bold'])
        ws.write('B11', ', '.join([l for l in product_type_name]))
        ws.write('A12', 'Product Category(s)', self.styles['bold'])
        ws.write('B12', ', '.join([l.complete_name for l in report.product_categ_ids]))
        ws.write('A13', 'Product(s)', self.styles['bold'])
        ws.write('B13', ', '.join([l.name for l in report.product_ids]))
        
        ws.write('A14', 'Expiry Date', self.styles['bold'])
        ws.write('B14', report.display_expiry_date)
        ws.write('A15', 'Group By Product Category', self.styles['bold'])
        ws.write('B15', report.group_product_categ)
        
        
    def get_timerange(self, report):
        """
        @param report: report object
        @return: Time range based on period.
        eg:  01/01/2017 - 03/01/2017 will return ['01/01/2017', '02/01/2017', '03/01/2017'] with period is daily
        """
        date_range = []
        period = report.period
        start_date = datetime.strptime(report.start_date, DATE_FORMAT)
        end_date = datetime.strptime(report.end_date, DATE_FORMAT)
        day_lap = timedelta(days=1)
        while start_date <= end_date:
            if period == 'daily':
                if start_date.strftime('%Y-%m-%d') not in date_range:
                    date_range.append(start_date.strftime('%Y-%m-%d'))
            elif period == 'weekly':
                if start_date.strftime('%W-%Y') not in date_range:
                    date_range.append(start_date.strftime('%W-%Y'))
            elif period == 'monthly':
                if start_date.strftime('%m-%Y') not in date_range:
                    date_range.append(start_date.strftime('%m-%Y'))
            elif period == 'quarterly':
                quarter = "Q%s-%s" % ( ((start_date.month - 1) // 3) + 1 , start_date.year)
                if quarter not in date_range:
                    date_range.append(quarter)
            start_date += day_lap
        return date_range
 
    def get_report_styles(self, wb):
        styles = {}
        styles['bold_right_big'] = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
 
        styles['bold'] = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
 
        styles['right'] = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman'
        })
 
        styles['center'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Times New Roman'
        })
 
        styles['date_left'] = wb.add_format({
            'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy',
        })
 
        styles['table_header'] = wb.add_format({
            'bold': 1,
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
        })
 
        styles['table_row_left'] = wb.add_format({
            #'text_wrap': 1,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
        })
 
        styles['table_row_right'] = wb.add_format({
            'text_wrap': 1,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })
 
        styles['table_row_center'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'font_name': 'Times New Roman',
        })
 
        styles['table_row_date'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy',
        })
 
        styles['table_row_time'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'hh:mm:ss',
        })
 
        styles['table_row_datetime'] = wb.add_format({
            'text_wrap': 1,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_name': 'Times New Roman',
            'num_format': 'dd/mm/yyyy hh:mm:ss',
        })
        styles['qty_value_merge_header'] = wb.add_format({
                    'font_color': 'red',
                    'bold': 1,
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    })
        styles['date_merge_cell_header'] = wb.add_format({
                    'bold': 1,
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#ffc966'})
        styles['date_merge_cell_header_qty'] = wb.add_format({
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#ffe4b2'})
        styles['date_merge_cell_header_value'] = wb.add_format({
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#eee9e9'})
        
        styles['wh_loc_merge_cell_header'] = wb.add_format({
                    'bold': 1,
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#ffcc00'})
        styles['balance_merge_cell_header'] = wb.add_format({
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#b2b2b2'})
        styles['value_cell_header'] = wb.add_format({
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#cccccc'})
        return styles
 
    def get_locations(self, report):
        locations = report.location_ids
        stock_location = self.env['stock.location']
        if not locations:
            if report.warehouse_ids:
                view_locations = [x.view_location_id.id for x in report.warehouse_ids]
                locations = stock_location.search([('id', 'child_of', view_locations)])
        return locations

    def get_flush_date(self):
        """
        Get the latest flush date.
        """
        latest_flush_date = self.env['stock.flush.date'].search(
            [], order='flush_date desc', limit=1)
        if latest_flush_date:
            return latest_flush_date.flush_date
        return False
    
    # this method only for specific location type
    def get_specific_locations(self, report):
        src_locations = False
        dest_locations = False
        if report.location_type == 'specific':
            stock_location = self.env['stock.location']
            if report.movement_type == 'incoming':
                src_locations = report.in_source_location_ids
                if not src_locations:
                    if report.in_source_warehouse_ids:
                        view_locations = [x.view_location_id.id for x in report.in_source_warehouse_ids]
                        src_locations = stock_location.search([('id', 'child_of', view_locations)])
                
                dest_locations = report.in_destination_location_ids
                if not dest_locations:
                    if report.in_destination_warehouse_id:
                        view_locations = [report.in_destination_warehouse_id.view_location_id.id]
                        dest_locations = stock_location.search([('id', 'child_of', view_locations)])
            
            if report.movement_type == 'outgoing':
                src_locations = report.out_source_location_ids
                if not src_locations:
                    if report.out_source_warehouse_id:
                        view_locations = [report.out_source_warehouse_id.view_location_id.id]
                        src_locations = stock_location.search([('id', 'child_of', view_locations)])
                
                dest_locations = report.out_destination_location_ids
                if not dest_locations:
                    if report.out_destination_warehouse_ids:
                        view_locations = [x.view_location_id.id for x in report.out_destination_warehouse_ids]
                        dest_locations = stock_location.search([('id', 'child_of', view_locations)]) 
        print "src_locations, dest_locations",src_locations, dest_locations
        return src_locations, dest_locations
 
#     def get_period_by_date(self, period, _date):
#         d = datetime.strptime(_date, DATE_FORMAT)
#         if period == 'daily':
#             return _date
#         elif period == 'weekly':
#             return d.strftime("%W-%Y")
#         elif period == 'monthly':
#             return d.strftime("%Y-%m")
#         elif period == 'quarterly':
#             return "%s-%s" % ((d.month - 1) // 3, d.year)
# 
    def get_data(self, domain, report):
        def key_by_period(_date):
            d = datetime.strptime(_date, DATE_FORMAT)
            if period == 'daily':
                return _date
            elif period == 'weekly':
                return d.strftime("%W-%Y")
            elif period == 'monthly':
                return d.strftime("%m-%Y")
            elif period == 'quarterly':
                return "%s-%s" % ((d.month - 1) // 3, d.year)

        period = report.period
        
        statements = {
            'select': self.select(report),
            'group_by': self.group_by(report),
            'where': self.where(report),
            'main_query': self.get_main_query(domain),
        }
        
        query = """
        WITH tmp AS (
            SELECT
              {select}
            FROM stock_move move
              LEFT JOIN stock_quant_move_rel ON move.id = stock_quant_move_rel.move_id
              LEFT JOIN stock_quant quant ON quant.id = stock_quant_move_rel.quant_id
              LEFT JOIN product_product pp ON move.product_id = pp.id
              LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
            {where}
            {group_by}
        ){main_query}
        """.format(**statements)

        _logger.info("query---> %s"%query)
        _logger.info("Q start time ---> %s"%datetime.now())
        self.env.cr.execute(query)
        _logger.info("Q end time ---> %s"%datetime.now())
        raw_data = self.env.cr.dictfetchall()
        
        res = OrderedDict()
        
        with_expiry = False
        if report.display_expiry_date == 'yes':
            with_expiry = True
        group_categ = False
        if report.group_product_categ == 'yes':
            group_categ = True

        for l in raw_data:
            if group_categ:
                k = '{product_category}'.format(
                    product_category=l['product_category']
                )
            elif with_expiry:
                k = '{removal_date}|{product_id}|{product_category}'.format(
                    removal_date=l.get('removal_date') and l['removal_date'].split(' ')[0] or '',
                    product_id=l['product_id'],
                    product_category=l['product_category']
                )
            else:
                k = '{product_id}|{product_category}'.format(
                    product_id=l['product_id'],
                    product_category=l['product_category']
                )
            if report.report_breakdown == 'by_period':
                date_key = key_by_period(l['date'])
            else:
                date_key = l['location_name']
            if k not in res:
                l['dates'] = {}
                l['dates'][date_key] = {
                    'qty_in': l['qty_in'] or 0,
                    'qty_out': l['qty_out'] or 0,
                    'value_in': l['value_in'] or 0,
                    'value_out': l['value_out'] or 0,
                }
                res[k] = l
            else:
                if date_key in res[k]['dates']:
                    res[k]['dates'][date_key]['qty_in'] += l['qty_in'] or 0
                    res[k]['dates'][date_key]['qty_out'] += l['qty_out'] or 0
                    res[k]['dates'][date_key]['value_in'] += l['value_in'] or 0
                    res[k]['dates'][date_key]['value_out'] += l['value_out'] or 0
                else:
                    res[k]['dates'][date_key] = {
                        'qty_in': l['qty_in'] or 0,
                        'qty_out': l['qty_out'] or 0,
                        'value_in': l['value_in'] or 0,
                        'value_out': l['value_out'] or 0
                    }
        return res
    
    def bind_data(self, ws, report_data, report):
        if report.report_breakdown == 'by_period':
            period_time_range = self.get_timerange(report)
        else:
            if report.location_type == 'fixed':
                period_time_range = [x.complete_name for x in self.get_locations(report)]
            if report.location_type == 'specific':
                source_loc , destination_loc = self.get_specific_locations(report)
                if report.movement_type == 'incoming':
                    period_time_range = [x.complete_name for x in source_loc]
                if report.movement_type == 'outgoing':
                    period_time_range = [x.complete_name for x in destination_loc]
                    
        period = report.period
        ws.set_column(0, 0, 35)
        ws.set_column(1, 2, 20)
        ws.set_column(3, 16000, 16)
        
        row = 14
                
        with_expiry = False
        if report.display_expiry_date == 'yes':
            with_expiry = True
        group_categ = False
        if report.group_product_categ == 'yes':
            group_categ = True
                    
        row += 1
        
        col = 0

        if group_categ:
            # group categ means only one column for category
            ws.write(row, col, 'Product Category', self.styles['table_header'])
            col += 1
        elif with_expiry:
            # with expiry means product, product_categ and expiry date
            ws.write(row, col, 'Product Category', self.styles['table_header'])
            col += 1
            ws.write(row, col, 'Product', self.styles['table_header'])
            col += 1
            ws.write(row, col, 'Expiry Date', self.styles['table_header'])
            col += 1
        else:
            # else means with product, product_categ 
            ws.write(row, col, 'Product Category', self.styles['table_header'])
            col += 1
            ws.write(row, col, 'Product', self.styles['table_header'])
            col += 1
            
        ws.write(row, col, 'UOM', self.styles['table_header'])
        col += 1
            
        
        header1_col = col #3
        header2_col = col #3
        for qv in ['Qty', 'Value']:
            if len(period_time_range) > 1:
                ws.merge_range(str(xlsxwriter.utility.xl_col_to_name(header1_col)+str(row) + ':'
                                   + xlsxwriter.utility.xl_col_to_name(header1_col+(len(period_time_range)-1))+str(row)),
                                    qv, self.styles['qty_value_merge_header'])
            else:
                ws.write(row-1, header2_col, qv, self.styles['qty_value_merge_header'])
            header1_col += len(period_time_range)
            
            for dt in period_time_range:
                if report.report_breakdown == 'by_location' and len(dt.split('/')) > 2:
                    dt = dt.split('/')[-2] + '/' + dt.split('/')[-1]
                ws.write(row, header2_col, dt, self.styles['date_merge_cell_header'])
                header2_col += 1
        
        row += 1
        
        
        for k in report_data.keys():
            col = 0
            line = report_data[k]
            
            if group_categ:
                # group categ means only one column for category
                ws.write(row, col, line['product_category'], self.styles['table_row_left'])
                col += 1
            elif with_expiry:
                # with expiry means product, product_categ and expiry date
                ws.write(row, col, line['product_category'], self.styles['table_row_left'])
                col += 1
                ws.write(row, col, line['product_name'], self.styles['table_row_left'])
                col += 1
                if line.get('removal_date'):
                    ws.write_datetime(row, col, datetime.strptime(line['removal_date'], DATETIME_FORMAT), self.styles['table_row_datetime'])
                col += 1
            else:
                # else means with product, product_categ 
                ws.write(row, col, line['product_category'], self.styles['table_row_left'])
                col += 1
                ws.write(row, col, line['product_name'], self.styles['table_row_left'])
                col += 1
                
            ws.write(row, col, line['default_supplier_uom'], self.styles['table_row_left'])
            col += 1
            
            if report.report_breakdown == 'by_period':
                for dt in period_time_range:
                    # here we use carry forward closing qty and value confirm with nicole.

                    if dt in line['dates']:

                        qty_in = line['dates'][dt]['qty_in'] or 0
                        qty_out = line['dates'][dt]['qty_out'] or 0
                        value_in = line['dates'][dt]['value_in'] or 0
                        value_out = line['dates'][dt]['value_out'] or 0
                    else:
                        qty_in = 0
                        qty_out = 0
                        value_in = 0
                        value_out = 0
    

                    if report.location_type == 'fixed':
                        if report.movement_type == 'incoming':
                            ws.write(row, col, float(round(qty_in,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_in,2)), self.styles['date_merge_cell_header_value'])
                        if report.movement_type == 'outgoing':
                            ws.write(row, col, float(round(qty_out * -1 ,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_out * -1 ,2)), self.styles['date_merge_cell_header_value'])
                    if report.location_type == 'specific':
                        if report.movement_type == 'incoming':
                            ws.write(row, col, float(round(qty_out * -1 ,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_out * -1 ,2)), self.styles['date_merge_cell_header_value'])
                        if report.movement_type == 'outgoing':
                            ws.write(row, col, float(round(qty_in,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_in,2)), self.styles['date_merge_cell_header_value'])
                    col += 1
            else:
                for dt in period_time_range:

                    if dt in line['dates']:

                        qty_in = line['dates'][dt]['qty_in'] or 0
                        qty_out = line['dates'][dt]['qty_out'] or 0
                        value_in = line['dates'][dt]['value_in'] or 0
                        value_out = line['dates'][dt]['value_out'] or 0
                    else:
                        qty_in = 0
                        qty_out = 0
                        value_in = 0
                        value_out = 0
    

                    
                    if report.location_type == 'fixed':
                        if report.movement_type == 'incoming':
                            ws.write(row, col, float(round(qty_in,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_in,2)), self.styles['date_merge_cell_header_value'])
                    
                        if report.movement_type == 'outgoing':
                            ws.write(row, col, float(round(qty_out * -1 ,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_out * -1 ,2)), self.styles['date_merge_cell_header_value'])
                    if report.location_type == 'specific':
                        if report.movement_type == 'incoming':
                            ws.write(row, col, float(round(qty_out * -1 ,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_out * -1 ,2)), self.styles['date_merge_cell_header_value'])
                    
                        if report.movement_type == 'outgoing':
                            ws.write(row, col, float(round(qty_in,2)), self.styles['date_merge_cell_header_qty'])
                            ws.write(row, col+len(period_time_range), float(round(value_in,2)), self.styles['date_merge_cell_header_value'])
                    col += 1
            row += 1
        _logger.info("finish write ---> %s"%datetime.now())
# 
#     def get_query(self, args):
#         query = """
#         WITH tmp AS (
#             SELECT
#               {select}
#             FROM stock_move move
#               LEFT JOIN stock_quant_move_rel ON move.id = stock_quant_move_rel.move_id
#               LEFT JOIN stock_quant quant ON quant.id = stock_quant_move_rel.quant_id
#             {where}
#             {group_by}
#         ){main_query}
#         """.format(**args)
#         return query
# 
    def where(self, report):
        wheres = {
            'start_date': report.start_date,
            'end_date': report.end_date,
            'location_ids': '',
            'product_ids': '',
        }
 
        def _in_condition(obs):
            ids = ['(%s)' % p.id for p in obs]
            ids_string = ", ".join(ids)
            return ids_string
 
        product_templates = report.product_ids

        # if report.product_categ_ids and not product_templates:
        #     categ_ids = [x.id for x in report.product_categ_ids]
        #     product_templates = self.env['product.template'].search([('categ_id', 'child_of', categ_ids)])
 
        if product_templates:
            product_template_ids = [x.id for x in product_templates]
            products = self.env['product.product'].search([('product_tmpl_id', 'in', product_template_ids)])
            wheres['product_ids'] = _in_condition(products)

        if report.location_type == 'fixed':
            locations = self.get_locations(report)
            if locations:
                wheres['location_ids'] = _in_condition(locations)
            if wheres['location_ids']:
                wheres['location_ids'] = "AND (move.location_id = ANY (VALUES {location_ids}) OR move.location_dest_id = ANY (VALUES {location_ids}))".format(location_ids=wheres['location_ids'])
        
        if report.location_type == 'specific':
            source_locations, destination_locations = self.get_specific_locations(report)
            wheres['location_ids'] = """AND (move.location_id = ANY (VALUES {src_location_ids}) 
                                            AND 
                                            move.location_dest_id = ANY (VALUES {dest_location_ids})
                                            )""".format(src_location_ids=_in_condition(source_locations),dest_location_ids=_in_condition(destination_locations))
            
        
        if wheres['product_ids']:
            wheres['product_ids'] = "AND move.product_id = ANY (VALUES %s)" % wheres['product_ids']

        flush_date = self.get_flush_date()
        wheres['flush_date'] = "AND 1=1"
        if flush_date:
            wheres[
                'flush_date'] = "AND (pt.is_asset OR move.date >= '%s')" % flush_date

        if report.base_on_date == 'move_date':
            where_sql = """WHERE
                date(move.date + INTERVAL '8 HOURS') <= date('{end_date}')
                {location_ids}
                {product_ids}
                {flush_date}
                AND move.state = 'done'
            """.format(**wheres)
        elif report.base_on_date == 'expected_date':
            where_sql = """WHERE
                            date(move.date_expected + INTERVAL '8 HOURS') <= date('{end_date}')
                            {location_ids}
                            {product_ids}
                            {flush_date}
                            AND move.state = 'done'
                        """.format(**wheres)
        return where_sql
# 
    def select(self, report):

        if report.base_on_date == 'move_date':
            date_select = "move.date + INTERVAL '8 HOURS'     AS date,"
        elif report.base_on_date == 'expected_date':
            date_select = "move.date_expected + INTERVAL '8 HOURS'     AS date,"

        select_str = """
           move.product_uom,
           move.picking_id,
           move.state,
           move.origin,
           move.location_id                   AS source_location_id,
           move.location_dest_id              AS destination_location_id,
           quant.lot_id,
           quant.vendor_id,
           move.product_id,
           CASE WHEN quant.cost IS NOT NULL THEN quant.cost ELSE 0 END                        AS value,
           SUM(CASE WHEN quant.qty > 0 THEN quant.qty ELSE 0 END) AS qty,
           {date_select}
           move.date_expected + INTERVAL '8 HOURS' AS date_expected
           """.format(date_select=date_select)
        return select_str

    def group_by(self, report):

        if report.base_on_date == 'move_date':
            date_group = "move.date"
        elif report.base_on_date == 'expected_date':
            date_group = "move.date_expected"

        group_by_str = """
        GROUP BY
          move.product_uom,
          move.picking_id,
          move.state,
          move.origin,
          move.location_id,
          move.location_dest_id,
          move.product_id,
          {date_group},
          move.date_expected,
          quant.lot_id,
          quant.vendor_id,
          quant.cost
        """.format(date_group=date_group)
        return group_by_str
    
    def get_domain(self, report):
        uom_fields = {
            'standard': '1 = 2',
            'distribution': 'supplier_uom.is_distribution = TRUE',
            'storage': 'supplier_uom.is_storage = TRUE',
            'purchase': 'supplier_uom.is_po_default = TRUE',
        }
        domain = {
            'start_date': report.start_date,
            'end_date': report.end_date,
            'uom_type_cond': uom_fields[report.uom_type],
            'company_id' : self.env.user.company_id.id
        }
        if report.location_type == 'fixed':
            locations = self.get_locations(report)
            location_ids = ", ".join(['(%s)' % p.id for p in locations])
            if location_ids:
                location_ids =  location_ids
            domain['location_dest_ids'] = 'destination_location_id = ANY(values %s)' % location_ids if location_ids else '1=1'
            domain['location_src_ids'] = 'source_location_id = ANY(values %s)' % location_ids if location_ids else '1=1'
        if report.location_type == 'specific':
            source_locations, destination_locations = self.get_specific_locations(report)
            source_location_ids = ", ".join(['(%s)' % p.id for p in source_locations])
            destination_location_ids = ", ".join(['(%s)' % p.id for p in destination_locations])
            domain['location_dest_ids'] = 'destination_location_id = ANY(values %s)' % destination_location_ids if destination_location_ids else '1=1'
            domain['location_src_ids'] = 'source_location_id = ANY(values %s)' % source_location_ids if source_location_ids else '1=1'
        
        return domain

    # NOTE: This method does not return product type and also change current report object
    def get_product(self, report):
        product_type = []
        if report.type_stockable:
            product_type.append('product')
        if report.type_consumable:
            product_type.append('consu')
        if report.type_service:
            product_type.append('service')

        if not report.product_categ_ids:
            product_id = self.env['product.template'].search([('type', 'in', product_type)])

        if report.product_categ_ids:
            product_id = self.env['product.template'].search(['&', ('categ_id', 'child_of', [x.id for x in report.product_categ_ids]), ('type', 'in', product_type)])

        if product_id:
            report.product_ids = product_id.ids

    def get_product_type_name(self, report):
        product_type_name = []
        if report.type_stockable:
            product_type_name.append('Stockable')
        if report.type_consumable:
            product_type_name.append('Consumable')
        if report.type_service:
            product_type_name.append('Service')
        return product_type_name

    def get_main_query(self, domain):
        main_query = """
        , foo AS (
            SELECT
                destination_location_id AS location_id,
                lot_id,
                vendor_id,
                product_id,
                value,
                qty,
                date
            FROM tmp
            WHERE {location_dest_ids}
            UNION ALL
            SELECT
                source_location_id AS location_id,
                lot_id,
                vendor_id,
                product_id,
                value,
                -1 * qty,
                date
            FROM tmp
            WHERE {location_src_ids}
        ), moves AS (
            SELECT
                location_id,
                lot_id,
                vendor_id,
                product_id,
                SUM(CASE WHEN qty < 0 THEN qty * value ELSE 0 END) AS value_out,
                SUM(CASE WHEN qty > 0 THEN qty * value ELSE 0 END) AS value_in,
                SUM(qty) AS qty,
                SUM(CASE WHEN qty < 0 THEN qty ELSE 0 END) AS qty_out,
                SUM(CASE WHEN qty > 0 THEN qty ELSE 0 END) AS qty_in,
                date(date) as date
            FROM foo
            WHERE date(foo.date) >= date('{start_date}')
            GROUP BY
                location_id,
                lot_id,
                vendor_id,
                product_id,
                date(date)
        )
        SELECT
          location.id AS location_id,
          lot.id AS lot_id,
          product.id AS product_id,
          warehouse.name                     AS warehouse_name,
          location.complete_name             AS location_name,
          product_category.complete_name     AS product_category,
          product.name_template              AS product_name,
          lot.name                           AS lot_name,
          lot.removal_date::TIMESTAMP(0) + INTERVAL '8 HOURS' AS removal_date,
          lot.create_date::TIMESTAMP(0) + INTERVAL '8 HOURS'  AS into_system_date,
          CASE  WHEN barz.name IS NOT NULL 
                THEN barz.name 
                WHEN default_supplier.name IS NOT NULL 
                THEN default_supplier.name
                ELSE base_uom.name END AS uom,
          
          CASE WHEN default_supplier.name IS NOT NULL THEN default_supplier.name ELSE base_uom.name END AS default_supplier_uom,
          
          CASE  WHEN barz.name IS NOT NULL 
                THEN barz.supplier_name 
                WHEN default_supplier.name IS NOT NULL 
                THEN default_supplier.supplier_name
                ELSE base_supplier.name END AS supplier,
          
          CASE  WHEN barz.factor IS NOT NULL 
                THEN moves.qty_out / barz.factor 
                WHEN default_supplier.factor IS NOT NULL 
                THEN moves.qty_out / default_supplier.factor
                ELSE moves.qty_out END AS qty_out,
          moves.value_out AS value_out,
          CASE  WHEN barz.factor IS NOT NULL 
                THEN moves.qty_in / barz.factor
                WHEN default_supplier.factor IS NOT NULL 
                THEN moves.qty_in / default_supplier.factor 
                ELSE moves.qty_in END AS qty_in,
          moves.value_in AS value_in,
          moves.date AS date
        FROM moves
          
          INNER JOIN stock_location location ON moves.location_id = location.id 
          LEFT JOIN stock_location parent_location
            ON parent_location.parent_left < location.parent_left
               AND parent_location.parent_right > location.parent_left
               AND location.id != parent_location.location_id
               AND parent_location.usage = 'view'
          LEFT JOIN stock_warehouse warehouse ON parent_location.id = warehouse.view_location_id
          INNER JOIN product_product product ON moves.product_id = product.id 
          INNER JOIN product_template ON product_template.id = product.product_tmpl_id
          INNER JOIN product_category ON product_template.categ_id = product_category.id
          LEFT JOIN stock_production_lot lot ON moves.lot_id = lot.id 
          LEFT JOIN (
            SELECT
               supplierinfo.product_tmpl_id,
               supplierinfo.is_default,
               supplier_uom.name,
               supplier.name AS supplier_name,
               supplier.id as supplier_id,
               case when supplier_uom.uom_type in ('smaller','reference') then 
                        supplier_uom.factor 
                    when supplier_uom.uom_type in ('bigger') then
                        1/supplier_uom.factor 
               end AS factor
            FROM
               product_supplierinfo supplierinfo
              INNER JOIN product_uom supplier_uom ON supplierinfo.id = supplier_uom.vendor_id
              AND {uom_type_cond}
              LEFT JOIN res_partner supplier ON supplierinfo.name = supplier.id 
              where supplierinfo.company_id = {company_id}
          ) barz ON 
                case 
                    when moves.vendor_id is not null then
                        product_template.id = barz.product_tmpl_id AND moves.vendor_id = barz.supplier_id 
                    else
                        1=2 
                end
        LEFT JOIN (
            SELECT
               supplierinfo.product_tmpl_id,
               supplierinfo.is_default,
               supplier_uom.name,
               supplier.name AS supplier_name,
               supplier.id as supplier_id,
               case when supplier_uom.uom_type in ('smaller','reference') then 
                        supplier_uom.factor 
                    when supplier_uom.uom_type in ('bigger') then
                        1/supplier_uom.factor 
               end AS factor
            FROM
               product_supplierinfo supplierinfo
              INNER JOIN product_uom supplier_uom ON supplierinfo.id = supplier_uom.vendor_id
              AND {uom_type_cond}
              LEFT JOIN res_partner supplier ON supplierinfo.name = supplier.id 
              where supplierinfo.company_id = {company_id}
          ) default_supplier ON 
          product_template.id = default_supplier.product_tmpl_id and default_supplier.is_default = True 
          LEFT JOIN product_uom base_uom ON product_template.uom_id = base_uom.id
          LEFT JOIN product_supplierinfo base_supplierinfo ON base_uom.vendor_id = base_supplierinfo.id
          LEFT JOIN res_partner base_supplier ON base_supplierinfo.name = base_supplier.id
        ORDER BY
            warehouse.name,
            location.complete_name,
            product_category.complete_name,
            product.name_template,
            moves.date,
            lot.name

        """.format(**domain)
        return main_query

stock_inventory_movement_report('report.inventory_movement_report.stock_inventory_movement_report', 'inventory.movement.report')