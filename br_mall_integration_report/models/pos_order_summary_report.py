import logging
import pytz
from datetime import datetime

from dateutil.relativedelta import relativedelta
from openerp.addons.report_txt.report.report_txt import ReportTxt

from openerp import models, fields, api
from openerp.exceptions import UserError
from openerp.osv import osv
from openerp.tools.translate import _
from openerp.tools import float_round

logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def convert_timezone(from_tz, to_tz, dt):
    from_tz = pytz.timezone(from_tz).localize(datetime.strptime(dt, DATETIME_FORMAT))
    to_tz = from_tz.astimezone(pytz.timezone(to_tz))
    return to_tz.strftime(DATETIME_FORMAT)


class gto_summary_report(models.Model):
    _name = 'gto.summary.report'
    date = fields.Date('Date')
    from_date = fields.Date('From Date')
    outlet_ids = fields.Many2one(string=_("Outlet"), comodel_name='br_multi_outlet.outlet')

    @api.multi
    def action_print(self):
        # self.env['ftp.gto.summary'].ftp_gto_summary()
        return self.env['report'].get_action(self, 'br_mall_integration_report.gto_summary_data')

    @api.model
    def get_data(self):
        to_date = self.date
        if self.from_date:
            from_date = self.from_date
        else:
            previous_date = datetime.strptime(to_date, '%Y-%m-%d') - relativedelta(days=1)
            from_date = datetime.strftime(previous_date, '%Y-%m-%d')

        cond = """ where (po.is_refund <> 'true' AND po.is_refunded <> 'true' )
            and ps.start_at between '{from_date} 21:00:00' and '{to_date} 21:00:00'
            and po.outlet_id = {outlet_id}
        """.format(from_date=from_date, to_date=to_date, outlet_id=self.outlet_ids.id)

        sql = """
        select
  COALESCE(sum(round(pol.qty * pol.price_unit, 2) +  round(round(pol.qty * pol.price_unit, 2) * (CASE WHEN tax.price_include = FALSE THEN tax.amount / 100 ELSE 0 END), 2)), 0)                          AS total,
  COALESCE(sum(round(pol.qty * pol.price_unit, 2)) -
           sum(round(round(pol.qty * pol.price_unit, 2) / (1 + tax.amount / 100) * (CASE WHEN tax.price_include = TRUE
             THEN tax.amount / 100
                                                                                    ELSE 0 END), 2)), 0) AS before_tax,
  COALESCE(sum(round(round(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE
    THEN tax.amount / 100
                                                               ELSE 0 END) * (tax.amount / 100), 2)), 0) AS tax,
  COALESCE(round(sum(pol.discount_amount + pol.discount_amount * (CASE WHEN tax.price_include = FALSE
    THEN tax.amount / 100
                                                                  ELSE 0 END)), 2), 0)                   AS discount,
  COUNT(DISTINCT
      po.id)                                                                                             AS ticket_count,
  COALESCE(round(sum(pol.discount_amount / (1 + CASE WHEN tax.price_include = TRUE
    THEN tax.amount / 100
                                                ELSE 0 END)), 2),
           0)                                                                                            AS discount_before_tax
        from pos_order_line pol
        inner join pos_order po on po.id = pol.order_id
        inner join pos_session ps ON po.session_id = ps.id
        left join account_tax_pos_order_line_rel tax_rel on tax_rel.pos_order_line_id = pol.id
        left join account_tax tax on tax.id = tax_rel.account_tax_id        
        %s
        and pol.non_sale = FALSE
        """ % cond

        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        tax_adjustment = self.get_tax_adjustment(cond)
        redemption_amount = self.get_redemption_amount(cond)
        if data:
            # Remove tax adjustment
            data[0]['tax'] += tax_adjustment
            data[0]['before_tax'] -= tax_adjustment
            # Remove redemption amount
            data[0]['total'] -= redemption_amount['total']
            data[0]['before_tax'] -= redemption_amount['before_tax']
            data[0]['tax'] -= redemption_amount['tax']
            data[0]['ticket_count'] -= redemption_amount['ticket_count']
        return data

    def get_tax_adjustment(self, cond):
        self.env.cr.execute("""
                    SELECT COALESCE(SUM(tax_adjustment), 0)
                    FROM pos_order po
                     INNER JOIN pos_session ps ON po.session_id = ps.id
                    %s
                """ % cond)
        data = self.env.cr.fetchone()
        if data:
            return float(data[0])
        return 0

    def get_redemption_amount(self, cond):
        # TODO: Dear tomorrow me, MOVE THIS TO br_discount MODULE
        self.env.cr.execute("""                    
            WITH tmp AS (
                SELECT
                  COALESCE(SUM(poslvd.value + poslvd.unredeem_value), 0)                                                                     AS total,
                  COALESCE(SUM(round((poslvd.value + poslvd.unredeem_value) / (1 + tax.amount / 100), 2)), 0)                                  AS before_tax,
                  COALESCE(SUM(poslvd.value + poslvd.unredeem_value), 0) - COALESCE(SUM(round((poslvd.value + poslvd.unredeem_value) / (1 + tax.amount / 100), 2)), 0) AS tax,
                  CASE WHEN COALESCE(SUM(poslvd.value), 0) >= MAX(po.origin_total)
                    THEN 1
                  ELSE 0 END                                                                                         AS ticket_count
                FROM pos_order po
                  INNER JOIN pos_order_sale_voucher_detail poslvd ON po.id = poslvd.order_id
                  INNER JOIN account_account ON poslvd.tax_account_id = account_account.id
                  INNER JOIN account_tax tax ON account_account.id = tax.account_id
                  INNER JOIN pos_session ps ON po.session_id = ps.id
                  %s
                GROUP BY poslvd.order_id
            ) SELECT
                COALESCE(SUM(total), 0)        AS total,
                COALESCE(SUM(before_tax), 0)   AS before_tax,
                COALESCE(SUM(tax), 0)          AS tax,
                COALESCE(SUM(ticket_count), 0) AS ticket_count
              FROM tmp;
        """ % cond)
        data = self.env.cr.dictfetchone()
        return data

    @api.model
    def get_cash_data(self):
        from_date = to_date = self.date
        if self.from_date:
            previous_date = datetime.strptime(self.from_date, '%Y-%m-%d') + relativedelta(days=+1)
            from_date = datetime.strftime(previous_date, '%Y-%m-%d')
        sql = """
                select  
                    COALESCE(sum(round(bank_line.amount,2)), 0) as cash
                    from pos_session ps
                    inner join account_bank_statement bank on bank.id = ps.cash_register_id
                    inner join account_bank_statement_line bank_line on bank_line.statement_id = bank.id
                    where bank_line.date between '%s' and '%s' 
                    and ps.outlet_id = %d and bank_line.pos_statement_id is not null
            """ % (from_date, to_date, self.outlet_ids.id)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()
        return data

    @api.model
    def get_cash_data_hourly(self):
        from_date = to_date = self.date
        if self.from_date:
            previous_date = datetime.strptime(self.from_date, '%Y-%m-%d') + \
                            relativedelta(days=+1)
            from_date = datetime.strftime(previous_date, '%Y-%m-%d')

        sql = """
                    select  
                        date_part('hour', bank_line.pos_date_order + INTERVAL '8 HOURS') as hour,
                        COALESCE(sum(round(bank_line.amount,2)), 0) as cash
                        from pos_session ps
                        inner join account_bank_statement bank on bank.id = ps.cash_register_id
                        inner join account_bank_statement_line bank_line on bank_line.statement_id = bank.id
                        where bank_line.date between '%s' and '%s' 
                        and ps.outlet_id = %d and bank_line.pos_statement_id is not null
                        group by date_part('hour', bank_line.pos_date_order + INTERVAL '8 HOURS')
                """ % (from_date, to_date, self.outlet_ids.id)
        self.env.cr.execute(sql)
        data = self.env.cr.dictfetchall()

        # reformat the data
        hour_cash = {}
        for cash_data in data:
            hour_cash[int(cash_data['hour'])] = cash_data['cash']
        return hour_cash

    @api.model
    def get_onsite_total_quantity(self, cond):
        tq_onsite = """
                        with total_qty as (
                            select 1 as qty
                            from br_pos_order_line_master pol
                            inner join pos_order po on po.id = pol.order_id
                            inner join pos_session ps on po.session_id = ps.id
                            left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                            left join account_journal aj on aj.id =  absl.journal_id
                            %s
                            and aj.payment_type = 'on_site'
                            group by pol.id
                        )
                        select sum(qty) as total_quantity_on_site
                        from total_qty
                        """ % cond
        self.env.cr.execute(tq_onsite)
        result = self.env.cr.dictfetchall()
        return result and result[0] or {}

    @api.model
    def get_offsite_total_quantity(self, cond):
        tq_offsite = """
                        with total_qty as (
                            select 1 as qty
                            from br_pos_order_line_master pol
                            inner join pos_order po on po.id = pol.order_id
                            inner join pos_session ps on po.session_id = ps.id
                            left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                            left join account_journal aj on aj.id =  absl.journal_id
                            %s
                            and aj.payment_type = 'off_site'
                            group by pol.id
                        )
                        select sum(qty) as total_quantity_off_site
                        from total_qty
                        """ % cond
        self.env.cr.execute(tq_offsite)
        result = self.env.cr.dictfetchall()
        return result and result[0] or {}

    @api.model
    def get_total_quantity(self, cond):
        total_tq = """
                        with total_qty as (
                            select 1 as qty
                            from br_pos_order_line_master pol
                            inner join pos_order po on po.id = pol.order_id
                            inner join pos_session ps on po.session_id = ps.id
                            left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                            left join account_journal aj on aj.id =  absl.journal_id
                            %s
                            and aj.payment_type in ('on_site', 'off_site')
                            group by pol.id
                        )
                        select sum(qty) as total_quantity
                        from total_qty
                        """ % cond
        self.env.cr.execute(total_tq)
        result = self.env.cr.dictfetchall()
        return result and result[0] or {}

    @api.model
    def get_onsite_ticket(self, cond):
        count_onsite = """
                        select  
                            count(distinct(po.id)) as total_on_site
                        from pos_order po
                        left join pos_session ps ON po.session_id = ps.id
                        left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                        left join account_journal aj on aj.id =  absl.journal_id
                        
                        %s
                        and aj.payment_type = 'on_site' and aj.is_rounding_method = False
                        
                        """%cond
        self.env.cr.execute(count_onsite)
        result = self.env.cr.dictfetchall()
        return result and result[0] or {}

    @api.model
    def get_offsite_ticket(self, cond):
        count_offsite = """
                        select  
                            count(distinct(po.id)) as total_off_site
                        from pos_order po
                        left join pos_session ps ON po.session_id = ps.id
                        left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                        left join account_journal aj on aj.id =  absl.journal_id
                        
                        %s
                        and aj.payment_type = 'off_site' and aj.is_rounding_method = False
                        
                        """%cond
        self.env.cr.execute(count_offsite)
        result = self.env.cr.dictfetchall()
        return result and result[0] or {}

    @api.model
    def get_total_ticket(self, cond):
        count_ticket = """
                            select  
                                count(distinct(po.id)) as total_ticket
                            from pos_order po
                            left join pos_session ps ON po.session_id = ps.id
                            left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                            left join account_journal aj on aj.id =  absl.journal_id

                            %s
                            and aj.payment_type in ('on_site','off_site') and aj.is_rounding_method = False

                            """ % cond
        self.env.cr.execute(count_ticket)
        result = self.env.cr.dictfetchall()
        return result and result[0] or {}

    @api.model
    def get_total_tax(self, cond):
        total_tax = """

                        select 
                            COALESCE(sum(round(round(pol.qty * pol.price_unit, 2) / (1 + CASE WHEN tax.price_include = TRUE
                            THEN tax.amount / 100
                            ELSE 0 END) * (tax.amount / 100), 2)), 0) AS tax

                        from pos_order_line pol
                        inner join pos_order po on po.id = pol.order_id
                        inner join pos_session ps ON po.session_id = ps.id
                        left join account_tax_pos_order_line_rel tax_rel on tax_rel.pos_order_line_id = pol.id
                        left join account_tax tax on tax.id = tax_rel.account_tax_id 
                        %s
                        """ % cond

        self.env.cr.execute(total_tax)
        result = self.env.cr.dictfetchall()

        return result and result[0] or {}

    @api.model
    def get_onsite_offsite_data(self):
        to_date = self.date
        if self.from_date:
            from_date = self.from_date
        else:
            previous_date = datetime.strptime(to_date, '%Y-%m-%d') - relativedelta(days=1)
            from_date = datetime.strftime(previous_date, '%Y-%m-%d')

        cond = """ where (po.is_refund <> 'true' AND po.is_refunded <> 'true' )
                    and ps.start_at between '{from_date} 21:00:00' and '{to_date} 21:00:00'
                    and po.outlet_id = {outlet_id}
                """.format(from_date=from_date, to_date=to_date, outlet_id=self.outlet_ids.id)
        total_sale_by_payment_sql = """
                        
                        select  
                                aj.payment_type as payment_type,
                                sum(absl.amount) as total_amount, 
                                sum(case when aj.payment_type = 'on_site' then absl.amount else 0 end) as on_site_amount,
                                sum(case when aj.payment_type = 'off_site' then absl.amount else 0 end) as off_site_amount,
                                sum(case when aj.payment_type = 'redemption' then absl.amount else 0 end) as redemption_amount,
                                sum(case when aj.payment_type = 'on_site' and aj.is_rounding_method = False then absl.amount else 0 end) as on_site_without_rounding,
                                sum(case when aj.payment_type = 'off_site' and aj.is_rounding_method = False then absl.amount else 0 end) as off_site_without_rounding,
                                sum(case when aj.is_rounding_method = True then absl.amount else 0 end) as total_rounding
                        
                        from pos_order po
                        left join pos_session ps ON po.session_id = ps.id
                        left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                        left join account_journal aj on aj.id =  absl.journal_id
                        %s
                        group by aj.payment_type
                    
                    """% cond
        self.env.cr.execute(total_sale_by_payment_sql)
        result = self.env.cr.dictfetchall()
        # if len(result) == 0:
        #     raise osv.except_osv(_('Warning!'), _("Report missing data"))
        data = {'all_total' : 0, 'total_rounding': 0}
        for row in result:
            if row['payment_type'] == 'on_site':
                data['on_site'] = row['on_site_amount']
                data['all_total'] += row['on_site_amount']
                data['on_site_without_rounding'] = row['on_site_without_rounding']
            if row['payment_type'] == 'off_site':
                data['off_site'] = row['off_site_amount']
                data['all_total'] += row['off_site_amount']
                data['off_site_without_rounding'] = row['off_site_without_rounding']
            if row['payment_type'] == 'redemption':
                data['redemption'] = row['redemption_amount']
                data['all_total'] += row['redemption_amount']
            data['total_rounding'] += row['total_rounding']
        tax_data = self.get_total_tax(cond)
        tax_adjustment = self.get_tax_adjustment(cond)
        cash = self.get_cash_data()[0]['cash'] or 0
        tax = (tax_data.get('tax') and tax_data['tax'] or 0) + (tax_adjustment)
        total_net_sale = (data['all_total'] + (data['total_rounding'] * -1) ) - tax

        net_on_site_excl_tax = float_round((data.get('on_site') and data['on_site'] or 0.0) / (data['all_total'] or 1) * total_net_sale, 2)
        net_off_site_excl_tax = float_round((data.get('off_site') and data['off_site'] or 0.0) / (data['all_total'] or 1) * total_net_sale, 2)

        data['on_site_with_tax'] = data.get('on_site_without_rounding') and data['on_site_without_rounding'] or 0
        data['off_site_with_tax'] = data.get('off_site_without_rounding') and data['off_site_without_rounding'] or 0

        data['on_site_without_tax'] = net_on_site_excl_tax
        data['off_site_without_tax'] = net_off_site_excl_tax

        data['on_site_tax'] = float_round((data.get('on_site_without_rounding') and data['on_site_without_rounding'] or 0) - net_on_site_excl_tax, 2)
        data['off_site_tax'] = float_round((data.get('off_site_without_rounding') and data['off_site_without_rounding'] or 0) - net_off_site_excl_tax, 2)

        data['cash_wo_tax'] = float_round(cash / (data['all_total'] or 1) * total_net_sale, 2)

        onsite_tc_count = self.get_onsite_ticket(cond)
        data['onsite_tc'] = onsite_tc_count.get('total_on_site') and onsite_tc_count['total_on_site'] or 0

        offsite_tc_count = self.get_offsite_ticket(cond)
        data['offsite_tc'] = offsite_tc_count.get('total_off_site') and offsite_tc_count['total_off_site'] or 0

        total_tc_count = self.get_total_ticket(cond)
        data['total_tc'] = total_tc_count.get('total_ticket') and total_tc_count['total_ticket'] or 0

        onsite_tq_count = self.get_onsite_total_quantity(cond)
        data['onsite_tq'] = onsite_tq_count.get('total_quantity_on_site') and \
                            onsite_tq_count['total_quantity_on_site'] or 0

        offsite_tq_count = self.get_offsite_total_quantity(cond)
        data['offsite_tq'] = offsite_tq_count.get('total_quantity_off_site') and \
                             offsite_tq_count['total_quantity_off_site'] or 0

        total_tq_count = self.get_total_quantity(cond)
        data['total_tq'] = total_tq_count.get('total_quantity') and \
                           total_tq_count['total_quantity'] or 0
        return data

    @api.model
    def get_onsite_offsite_data_hourly(self, hour, cash):
        to_date = self.date
        if self.from_date:
            from_date = self.from_date
        else:
            previous_date = datetime.strptime(to_date, '%Y-%m-%d') - \
                            relativedelta(days=1)
            from_date = datetime.strftime(previous_date, '%Y-%m-%d')

        to_datetime = datetime.strptime(to_date, DATE_FORMAT)
        start_datetime = datetime.strftime(
            to_datetime.replace(hour=hour, minute=0, second=0),
            DATETIME_FORMAT)
        end_datetime = datetime.strftime(
            to_datetime.replace(hour=hour, minute=59, second=59),
            DATETIME_FORMAT)

        start_datetime_tz = convert_timezone(self.env.user.tz, 'UTC',
                                             start_datetime)
        end_datetime_tz = convert_timezone(self.env.user.tz, 'UTC',
                                           end_datetime)

        cond = """ where (po.is_refund <> 'true' AND po.is_refunded <> 'true' )
                            and ps.start_at between '{from_date} 21:00:00' and '{to_date} 21:00:00'
                            and po.outlet_id = {outlet_id} and po.date_order between '{start_time}' and '{end_time}'
                        """.format(from_date=from_date, to_date=to_date,
                                   outlet_id=self.outlet_ids.id,
                                   start_time=start_datetime_tz,
                                   end_time=end_datetime_tz)
        total_sale_by_payment_sql = """

                            select  
                                    aj.payment_type as payment_type,
                                    sum(absl.amount) as total_amount, 
                                    sum(case when aj.payment_type = 'on_site' then absl.amount else 0 end) as on_site_amount,
                                    sum(case when aj.payment_type = 'off_site' then absl.amount else 0 end) as off_site_amount,
                                    sum(case when aj.payment_type = 'redemption' then absl.amount else 0 end) as redemption_amount,
                                    sum(case when aj.payment_type = 'on_site' and aj.is_rounding_method = False then absl.amount else 0 end) as on_site_without_rounding,
                                    sum(case when aj.payment_type = 'off_site' and aj.is_rounding_method = False then absl.amount else 0 end) as off_site_without_rounding,
                                    sum(case when aj.is_rounding_method = True then absl.amount else 0 end) as total_rounding

                            from pos_order po
                            left join pos_session ps ON po.session_id = ps.id
                            left join account_bank_statement_line absl on po.id = absl.pos_statement_id
                            left join account_journal aj on aj.id =  absl.journal_id
                            %s
                            group by aj.payment_type

                        """ % cond
        self.env.cr.execute(total_sale_by_payment_sql)
        result = self.env.cr.dictfetchall()
        # if len(result) == 0:
        #     raise osv.except_osv(_('Warning!'), _("Report missing data"))
        data = {'all_total': 0, 'total_rounding': 0}
        for row in result:
            if row['payment_type'] == 'on_site':
                data['on_site'] = row['on_site_amount']
                data['all_total'] += row['on_site_amount']
                data['on_site_without_rounding'] = row[
                    'on_site_without_rounding']
            if row['payment_type'] == 'off_site':
                data['off_site'] = row['off_site_amount']
                data['all_total'] += row['off_site_amount']
                data['off_site_without_rounding'] = row[
                    'off_site_without_rounding']
            if row['payment_type'] == 'redemption':
                data['redemption'] = row['redemption_amount']
                data['all_total'] += row['redemption_amount']
            data['total_rounding'] += row['total_rounding']
        tax_data = self.get_total_tax(cond)
        tax_adjustment = self.get_tax_adjustment(cond)
        tax = (tax_data.get('tax') and tax_data['tax'] or 0) + tax_adjustment
        total_net_sale = (data['all_total'] + (
                    data['total_rounding'] * -1)) - tax

        net_on_site_excl_tax = float_round(
            (data.get('on_site') and data['on_site'] or 0.0) / (
                        data['all_total'] or 1) * total_net_sale, 2)
        net_off_site_excl_tax = float_round(
            (data.get('off_site') and data['off_site'] or 0.0) / (
                        data['all_total'] or 1) * total_net_sale, 2)

        data['on_site_with_tax'] = data.get('on_site_without_rounding') and \
                                   data['on_site_without_rounding'] or 0
        data['off_site_with_tax'] = data.get('off_site_without_rounding') and \
                                    data['off_site_without_rounding'] or 0

        data['on_site_without_tax'] = net_on_site_excl_tax
        data['off_site_without_tax'] = net_off_site_excl_tax

        data['on_site_tax'] = float_round((data.get(
            'on_site_without_rounding') and data[
                                               'on_site_without_rounding'] or 0) - net_on_site_excl_tax,
                                          2)
        data['off_site_tax'] = float_round((data.get(
            'off_site_without_rounding') and data[
                                                'off_site_without_rounding'] or 0) - net_off_site_excl_tax,
                                           2)

        data['cash_wo_tax'] = float_round(
            cash / (data['all_total'] or 1) * total_net_sale, 2)

        onsite_tc_count = self.get_onsite_ticket(cond)
        data['onsite_tc'] = onsite_tc_count.get('total_on_site') and \
                            onsite_tc_count['total_on_site'] or 0

        offsite_tc_count = self.get_offsite_ticket(cond)
        data['offsite_tc'] = offsite_tc_count.get('total_off_site') and \
                             offsite_tc_count['total_off_site'] or 0

        total_tc_count = self.get_total_ticket(cond)
        data['total_tc'] = total_tc_count.get('total_ticket') and \
                           total_tc_count['total_ticket'] or 0

        onsite_tq_count = self.get_onsite_total_quantity(cond)
        data['onsite_tq'] = onsite_tq_count.get('total_quantity_on_site') and \
                            onsite_tq_count['total_quantity_on_site'] or 0

        offsite_tq_count = self.get_offsite_total_quantity(cond)
        data['offsite_tq'] = offsite_tq_count.get(
            'total_quantity_off_site') and \
                             offsite_tq_count['total_quantity_off_site'] or 0

        total_tq_count = self.get_total_quantity(cond)
        data['total_tq'] = total_tq_count.get('total_quantity') and \
                           total_tq_count['total_quantity'] or 0

        return data


class gto_summary_data(ReportTxt):
    _name = 'report.br_mall_integration_report.gto_summary_data'

    def generate_txt_report(self, wb, report, report_data):
        template_id = self.env['mall.template.summary.config'].search(
            [('outlet_ids', '=', report_data.outlet_ids.id), ('period', '=', 'daily')], limit=1)
        if not template_id:
            raise UserError(_('Your Outlet does not has GTO template. '
                              'Go to Point Of Sale -> Configuration -> Mall Integration Config to create Template\n'))
        result = ''
        report.name = 'unknown.txt'
        if template_id.file_format == 'hourly':
            cash_data = report_data.get_cash_data_hourly()
            total_hour = 24
            for hour in range(total_hour):
                template = template_id.position
                cash = cash_data.get(hour, 0)
                on_off_data = report_data.get_onsite_offsite_data_hourly(hour, cash)
                date_client = datetime.strptime(report_data.date, '%Y-%m-%d')
                format = {
                    'prefix': template_id.prefix,
                    'machine': template_id.machine,
                    'date': datetime.strftime(date_client,
                                              template_id.date_format or '%Y%m%d'),
                    'total': 0,
                    'before_tax': 0,
                    'cash': '%%0%s.2f' % (template_id.cash_padding + 3) % (
                                cash or 0),
                    'other': 0,
                    'discount': 0,
                    'gst': 0,
                    'total_quantity': 0,
                    'total_off_quantity': 0,
                    'total_on_off_quantity': 0,
                    'ticket_count': 0,
                    'ticket_off_site': 0,
                    'ticket_on_off': 0,
                    'sequence': '%%0%sd' % template_id.sequence_padding % template_id.sequence,
                    'filename_date': datetime.strftime(date_client,
                                                       template_id.filename_date_format or '%Y%m%d'),
                    'hour': '%02d' % hour

                }
                if on_off_data['on_site_with_tax'] is not None or on_off_data[
                    'off_site_with_tax'] is not None:
                    format.update({
                        'total': '%%0%s.2f' % (template_id.padding + 3) %
                                 on_off_data['on_site_with_tax'],
                        'total_on_off': '%%0%s.2f' % (
                                    template_id.padding + 3) % (
                                                on_off_data[
                                                    'on_site_with_tax'] +
                                                on_off_data[
                                                    'off_site_with_tax']),
                        'before_tax': '%%0%s.2f' % (
                                    template_id.before_gst_padding + 3) %
                                      on_off_data['on_site_without_tax'],
                        'before_tax_on_off': '%%0%s.2f' % (
                                    template_id.before_gst_padding + 3) % (
                                                     on_off_data[
                                                         'on_site_without_tax'] +
                                                     on_off_data[
                                                         'off_site_without_tax']),
                        'gst': '%%0%s.2f' % (template_id.gst_padding + 3) %
                               on_off_data['on_site_tax'],
                        'gst_on_off': '%%0%s.2f' % (
                                    template_id.gst_padding + 3) % (
                                              on_off_data['on_site_tax'] +
                                              on_off_data['off_site_tax']),
                        'discount': '%%0%s.2f' % (
                                    template_id.discount_padding + 3) % 0,
                        'total_quantity': '%%0%sd' % (
                                template_id.total_quantity_padding + 3) %
                                          on_off_data['onsite_tq'],
                        'total_off_quantity': '%%0%sd' % (
                                template_id.total_quantity_padding + 3) %
                                           on_off_data['offsite_tq'],
                        'total_on_off_quantity': '%%0%sd' % (
                                template_id.total_quantity_padding + 3) % (
                                             on_off_data['total_tq']),
                        'ticket_count': '%%0%sd' % (
                                    template_id.ticket_count_padding + 3) %
                                        on_off_data['onsite_tc'],
                        'ticket_off_site': '%%0%sd' % (
                                    template_id.ticket_count_padding + 3) %
                                           on_off_data['offsite_tc'],
                        'ticket_on_off': '%%0%sd' % (
                                    template_id.ticket_count_padding + 3) % (
                                         on_off_data['total_tc']),
                        'other': '%%0%s.2f' % (
                                    template_id.other_padding + 3) % (
                                             on_off_data[
                                                 'on_site_with_tax'] - cash),
                        'other_on_off': '%%0%s.2f' % (
                                    template_id.other_padding + 3) % (
                                                on_off_data[
                                                    'on_site_with_tax'] +
                                                on_off_data[
                                                    'off_site_with_tax'] - cash),
                        'other_wo_tax': '%%0%s.2f' % (
                                    template_id.other_padding + 3) % (
                                                on_off_data[
                                                    'on_site_without_tax'] -
                                                on_off_data['cash_wo_tax']),
                        'other_wo_tax_on_off': '%%0%s.2f' % (
                                    template_id.other_padding + 3) % (
                                                       on_off_data[
                                                           'on_site_without_tax'] +
                                                       on_off_data[
                                                           'off_site_without_tax'] -
                                                       on_off_data[
                                                           'cash_wo_tax']),
                        'cash_wo_tax': '%%0%s.2f' % (
                                    template_id.cash_padding + 3) % (
                                                   on_off_data[
                                                       'cash_wo_tax'] or 0)
                    })
                output = template.format(**format)
                output = output.encode('utf-8', 'ignore')
                result += (output + '\n')
                if template_id.name_file:
                    report.name = template_id.name_file.format(**format)
            wb.write(result)
        else:
            template = template_id.position
            on_off_data = report_data.get_onsite_offsite_data()
            #data = report_data.get_data()
            cash = report_data.get_cash_data()[0]['cash']
            date_client = datetime.strptime(report_data.date, '%Y-%m-%d')
            format = {
                'prefix': template_id.prefix,
                'machine': template_id.machine,
                'date': datetime.strftime(date_client, template_id.date_format or '%Y%m%d'),
                'total': 0,
                'before_tax': 0,
                'cash': '%%0%s.2f' % (template_id.cash_padding + 3) % (cash or 0),
                'other': 0,
                'discount': 0,
                'gst': 0,
                'total_quantity': 0,
                'total_off_quantity': 0,
                'total_on_off_quantity': 0,
                'ticket_count': 0,
                'ticket_off_site': 0,
                'ticket_on_off': 0,
                'sequence': '%%0%sd' % template_id.sequence_padding % template_id.sequence,
                'filename_date': datetime.strftime(date_client, template_id.filename_date_format or '%Y%m%d'),
                'hour': '%02d' % 0

            }
            if on_off_data['on_site_with_tax'] is not None or on_off_data['off_site_with_tax'] is not None:
                format.update({
                    'total': '%%0%s.2f' % (template_id.padding + 3) % on_off_data['on_site_with_tax'],
                    'total_on_off': '%%0%s.2f' % (template_id.padding + 3) % (
                            on_off_data['on_site_with_tax'] + on_off_data['off_site_with_tax']),
                    'before_tax': '%%0%s.2f' % (template_id.before_gst_padding + 3) % on_off_data['on_site_without_tax'],
                    'before_tax_on_off': '%%0%s.2f' % (template_id.before_gst_padding + 3) % (
                            on_off_data['on_site_without_tax'] + on_off_data['off_site_without_tax']),
                    'gst': '%%0%s.2f' % (template_id.gst_padding + 3) % on_off_data['on_site_tax'],
                    'gst_on_off': '%%0%s.2f' % (template_id.gst_padding + 3) % (
                            on_off_data['on_site_tax'] + on_off_data['off_site_tax']),
                    'discount': '%%0%s.2f' % (template_id.discount_padding + 3) % 0,
                    'total_quantity': '%%0%sd' % (template_id.total_quantity_padding + 3) % on_off_data['onsite_tq'],
                    'total_off_quantity': '%%0%sd' % (template_id.total_quantity_padding + 3) % on_off_data['offsite_tq'],
                    'total_on_off_quantity': '%%0%sd' % (template_id.total_quantity_padding + 3) % (on_off_data['total_tq']),
                    'ticket_count': '%%0%sd' % (template_id.ticket_count_padding + 3) % on_off_data['onsite_tc'],
                    'ticket_off_site': '%%0%sd' % (template_id.ticket_count_padding + 3) % on_off_data['offsite_tc'],
                    'ticket_on_off': '%%0%sd' % (template_id.ticket_count_padding + 3) % (on_off_data['total_tc']),
                    'other': '%%0%s.2f' % (template_id.other_padding + 3) % (on_off_data['on_site_with_tax'] - cash),
                    'other_on_off': '%%0%s.2f' % (template_id.other_padding + 3) % (
                            on_off_data['on_site_with_tax'] + on_off_data['off_site_with_tax'] - cash),
                    'other_wo_tax': '%%0%s.2f' % (template_id.other_padding + 3) % (
                            on_off_data['on_site_without_tax'] - on_off_data['cash_wo_tax']),
                    'other_wo_tax_on_off': '%%0%s.2f' % (template_id.other_padding + 3) % (
                            on_off_data['on_site_without_tax'] + on_off_data['off_site_without_tax'] -
                            on_off_data['cash_wo_tax']),
                    'cash_wo_tax': '%%0%s.2f' % (template_id.cash_padding + 3) % (on_off_data['cash_wo_tax'] or 0)
                })
            # if len(data) == 0:
            #     raise osv.except_osv(_('Warning!'), _("Report missing data"))
            output = template.format(**format)
            output = output.encode('utf-8', 'ignore')
            result += output
            if template_id.name_file:
                report.name = template_id.name_file.format(**format)
            wb.write(result)


gto_summary_data('report.br_mall_integration_report.gto_summary_data', 'gto.summary.report')
