from openerp.osv import osv
from openerp import fields
import pytz
import datetime
from openerp import tools
from openerp.addons.point_of_sale.report import pos_details


class br_pos_details(osv.osv_memory):
    _inherit = 'pos.details'

    def onchange_user_ids(self, cr, uid, ids, user_ids, email=False, context=None):
        outlets_domain = [('user_ids', 'in', [uid])]
        if user_ids:
            u_ids = []
            for x in user_ids:
                if x[0] == 4:
                    u_ids.append(x[1])
            if u_ids:
                outlets_domain.append(('user_ids', 'in', u_ids))
        return {'domain': {'outlet_ids': outlets_domain}}

    outlet_ids = fields.Many2many(comodel_name='br_multi_outlet.outlet', string='Outlet')

    def print_report(self, cr, uid, ids, context=None):
        """
         To get the date and print the report
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return : retrun report
        """
        if context is None:
            context = {}
        datas = {'ids': context.get('active_ids', [])}
        res = self.read(cr, uid, ids, ['date_start', 'date_end', 'user_ids', 'outlet_ids'], context=context)
        res = res and res[0] or {}
        datas['form'] = res
        if res.get('id',False):
            datas['ids']=[res['id']]
        return self.pool['report'].get_action(cr, uid, [], 'point_of_sale.report_detailsofsales', data=datas, context=context)

class pos_detailofsales(pos_details.pos_details):
    def __init__(self, cr, uid, name, context):
        super(pos_detailofsales, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_outlet_names': self._get_outlet_names
        })
    # Override
    def _pos_sales_details(self, form):
        pos_obj = self.pool.get('pos.order')
        user_obj = self.pool.get('res.users')
        data = []
        result = {}
        user_ids = form['user_ids'] or self._get_all_users()
        company_id = user_obj.browse(self.cr, self.uid, self.uid).company_id.id
        user = self.pool['res.users'].browse(self.cr, self.uid, self.uid)
        tz_name = user.tz or self.localcontext.get('tz') or 'UTC'
        user_tz = pytz.timezone(tz_name)
        between_dates = {}
        for date_field, delta in {'date_start': {'days': 0}, 'date_end': {'days': 1}}.items():
            timestamp = datetime.datetime.strptime(form[date_field] + ' 00:00:00',
                                                   tools.DEFAULT_SERVER_DATETIME_FORMAT) + datetime.timedelta(**delta)
            timestamp = user_tz.localize(timestamp).astimezone(pytz.utc)
            between_dates[date_field] = timestamp.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
        # Longdt start
        credentials =[
            ('date_order', '>=', between_dates['date_start']),
            ('date_order', '<', between_dates['date_end']),
            ('user_id', 'in', user_ids),
            ('state', 'in', ['done', 'paid', 'invoiced']),
            ('company_id', '=', company_id),
        ]

        if form['outlet_ids']:
            credentials.append(('outlet_id', 'in', form['outlet_ids']))
        pos_ids = pos_obj.search(self.cr, self.uid, credentials)
        pos_orders = pos_obj.browse(self.cr, self.uid, pos_ids, context=self.localcontext).filtered(
            lambda x: user.id in [u.id for u in x.outlet_id.user_ids])
        # Longdt end
        for pos in pos_orders:
            for pol in pos.lines:
                result = {
                    'code': pol.product_id.default_code,
                    'name': pol.product_id.name,
                    'invoice_id': pos.invoice_id.id,
                    'price_unit': pol.price_unit,
                    'qty': pol.qty,
                    'discount': pol.discount,
                    'total': (pol.price_unit * pol.qty * (1 - (pol.discount) / 100.0)),
                    'date_order': pos.date_order,
                    'pos_name': pos.name,
                    'uom': pol.product_id.uom_id.name
                }
                data.append(result)
                self.total += result['total']
                self.qty += result['qty']
                self.discount += result['discount']
        if data:
            return data
        else:
            return {}

    def _get_outlet_names(self, outlet_ids):
        outlet_pool = self.pool.get('br_multi_outlet.outlet')
        return ', '.join(map(lambda x: x.name, outlet_pool.browse(self.cr, self.uid, outlet_ids)))

class report_pos_detailofsales(osv.AbstractModel):
    _inherit = 'report.point_of_sale.report_detailsofsales'
    _wrapped_report_class = pos_detailofsales
