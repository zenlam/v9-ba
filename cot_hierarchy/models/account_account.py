from openerp import api, models, fields, _
from operator import itemgetter
from openerp.osv import expression
from openerp.exceptions import UserError, ValidationError
from datetime import datetime, date
import logging
_logger = logging.getLogger(__name__)


class account_account(models.Model):
    _inherit='account.account'

    def check_cycle(self, cr, uid, ids, context=None):
        """ climbs the ``self._table.parent_id`` chains for 100 levels or
        until it can't find any more parent(s)

        Returns true if it runs out of parents (no cycle), false if
        it can recurse 100 times without ending all chains
        """
        level = 100
        while len(ids):
            cr.execute('SELECT DISTINCT parent_id ' \
                       'FROM ' + self._table + ' ' \
                                               'WHERE id IN %s ' \
                                               'AND parent_id IS NOT NULL', (tuple(ids),))
            ids = map(itemgetter(0), cr.fetchall())
            if not level:
                return False
            level -= 1
        return True

#    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
#        """ Override search() to put account type filter"""
#        if context is None: context = {}
#        if not context.get('view_all', False):
#            args.append(eval('[' + "'type'," + "'!=', 'view']"))
#        return super(account_account, self)._search(cr, user, args, offset=offset, limit=limit, order=order, context=context,
#                                                count=count, access_rights_uid=access_rights_uid)

    @api.one
    @api.depends('level', 'parent_id')
    def _get_level(self):
        for account in self:
            # we may not know the level of the parent at the time of computation, so we
            # can't simply do res[account.id] = account.parent_id.level + 1
            level = 0
            parent = account.parent_id
            while parent:
                level += 1
                parent = parent.parent_id
            self.level = level

    @api.multi
    def _get_children_and_consol(self):
        # this function search for all the children and all consolidated children (recursively) of the given account ids
        ids = [val.id for val in self]
        ids2 = self.search([('parent_id', 'child_of', ids)])
        return ids2

    @api.one
    def _get_child_ids(self):
        for record in self:
            if record.child_parent_ids:
                child_ids = [x.id for x in record.child_parent_ids]
                self.child_id = child_ids
            else:
                self.child_id = []

    @api.multi
    def __compute(self):
        """ compute the balance, debit and/or credit for the provided
        account ids
        Arguments:
        `ids`: account ids
        `field_names`: the fields to compute (a list of any of
                       'balance', 'debit' and 'credit')
        `arg`: unused fields.function stuff
        `query`: additional query filter (as a string)
        `query_params`: parameters for the provided query string
                        (__compute will handle their escaping) as a
                        tuple
        """
        query = ''
        query_params = ()
        field_names = ['debit','credit','balance']
        mapping = {
            'balance': "COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance",
            'debit': "COALESCE(SUM(debit), 0) as debit",
            'credit': "COALESCE(SUM(credit), 0) as credit",
            # by convention, foreign_balance is 0 when the account has no secondary currency, because the amounts may be in different currencies
            'foreign_balance': "(SELECT CASE WHEN currency_id IS NULL THEN 0 ELSE COALESCE(SUM(amount_currency), 0) END FROM account_account WHERE id IN (account_id)) as foreign_balance",
        }
        # get all the necessary accounts
        children_and_consolidated = self._get_children_and_consol()
        # compute for each account the balance/debit/credit from the move lines
        accounts = {}
        res = {}
        if children_and_consolidated:
            tables, where_clause, where_params = self.env['account.move.line']._query_get()
            tables = tables.replace('"', '') if tables else "account_move_line"
            wheres = [""]
            if where_clause.strip():
                wheres.append(where_clause.strip())
            filters = " AND ".join(wheres)
            request = "SELECT account_id as id, " + ', '.join(mapping.values()) + \
                      " FROM " + tables + \
                      " WHERE account_id IN %s " \
                      + filters + \
                      " GROUP BY account_id"
            params = (tuple(children_and_consolidated._ids),) + tuple(where_params)
            self._cr.execute(request, params)

            for row in self._cr.dictfetchall():
                accounts[row['id']] = row

            # consolidate accounts with direct children
            children_and_consolidated = list(children_and_consolidated.ids)
            # children_and_consolidated.reverse()
            list(children_and_consolidated).reverse()
            brs = list(self.search([('id','in',children_and_consolidated)], order="id desc"))
            sums = {}
            currency_obj = self.env['res.currency']
            while brs:
                current = brs.pop(0)

#                 can_compute = True
#                 for child in current.child_id:
#                     if child.id not in sums:
#                         can_compute = False
#                         try:
#                             brs.insert(0, brs.pop(brs.index(child)))
#                         except ValueError:
#                             brs.insert(0, child)
#                 if can_compute:
                for fn in field_names:
                    sums.setdefault(current.id, {})[fn] = accounts.get(current.id, {}).get(fn, 0.0)
                    for child in current.child_id:
                        temp_val = 0
                        if sums.get(child.id) and sums[child.id].get(fn):
                            temp_val = sums[child.id][fn]
                        elif accounts.get(child.id) and accounts[child.id].get(fn):
                            temp_val = accounts[child.id][fn]
                        
                        if child.company_id.currency_id.id == current.company_id.currency_id.id:
                            sums[current.id][fn] += temp_val
                        else:
                            sums[current.id][fn] += currency_obj.compute(self._cr, self._uid, child.company_id.currency_id.id,
                                                                         current.company_id.currency_id.id,
                                                                         temp_val)

                    # as we have to relay on values computed before this is calculated separately than previous fields

            for acc in self:
                res = sums.get(acc.id,{})
                acc.debit = res.get('debit',0.0)
                acc.credit = res.get('credit',0.0)
                acc.balance = res.get('balance', 0.0)


# NOTE : This one remove from type selection from task : BASKIN-89 (YS request)
#     ('receivable', 'Receivable'),
#     ('payable', 'Payable'),
#     ('liquidity', 'Liquidity'),
#     ('consolidation', 'Consolidation'),
#     ('closed', 'Closed')
        
    type = fields.Selection([
        ('view', 'View'),
        ('other', 'Regular')
    ], 'Account Type', help="The 'Internal Type' is used for features available on " \
                                            "different types of accounts: view can not have journal items, consolidation are accounts that " \
                                            "can have children accounts for multi-company consolidations, payable/receivable are for " \
                                            "partners accounts (for debit/credit computations), closed for depreciated accounts.")
    parent_id = fields.Many2one('account.account', 'Parent', domain=[('type' ,'=' ,'view')])
    level = fields.Integer(string='Account Level',compute=_get_level, store=True )
    child_parent_ids = fields.One2many('account.account', 'parent_id', 'Children')
    child_id = fields.Many2many("account.account",compute=_get_child_ids, string="Child Accounts")
    balance = fields.Float(string = "Balance", compute =__compute, multi='balance')
    credit = fields.Float(compute=__compute, string='Credit', multi='balance')
    debit = fields.Float(compute=__compute,string='Debit', multi='balance')

    _check_recursion = check_cycle
    _constraints = [
        (_check_recursion, 'Error!\nYou cannot create recursive accounts.', ['parent_id'])
    ]


class AccountAccountType(models.Model):
    _inherit = "account.account.type"

    type = fields.Selection([
        ('other', 'Regular'),
        ('receivable', 'Receivable'),
        ('payable', 'Payable'),
        ('liquidity', 'Liquidity'),
        ('view','View'),
        ('asset','Asset View'),
        ('liability','Liability View'),
        ('expense','Expense View'),
        ('income','Income View'),
    ], required=True, default='other',
        help="The 'Internal Type' is used for features available on "\
        "different types of accounts: liquidity type is for cash or bank accounts"\
        ", payable/receivable is for vendor/customer accounts.")

class AccountTax(models.Model):
    _inherit = 'account.tax'

    tax_code_id = fields.Many2one('account.tax.code','Account Tax Code', help="Use this code for the tax declaration.")
    

class AccountTaxCode(models.Model):
    _name = 'account.tax.code'
    _rec_name = 'code'
    _order = 'sequence, code'

    def _default_company(self):
        if self.env.user.company_id:
            return self.env.user.company_id.id
        return self.env['res.company'].search([('parent_id', '=', False)])[0]

    @api.multi
    def _calc_total_tax_amount(self):
        AccountTaxCode = self.env['account.tax.code']
        context = self._context
        start_date = context.get('start_date', False)
        end_date = context.get('end_date', False)
        state = context.get('state', '')
        if state == 'posted':
            state = ('posted', )
        else:
            state = ('posted', 'draft')

        company_ids = []
        if self.env.user.company_id:
            company_ids.append(self.env.user.company_id.id)
            company_ids += self.env.user.company_ids.ids
            company_ids = list(set(company_ids))
        else:
            company_ids = self.env['res.company'].search([]).ids

        tax_codes_ids = self.search([('company_id', 'in', company_ids)]).ids

        self._cr.execute("""
            select atc.id, ABS(SUM(aml.credit-aml.debit)) as tax_amount
            from account_move_line as aml
            LEFT JOIN account_move am ON (am.id=aml.move_id)
            LEFT JOIN account_tax ata ON (ata.id=aml.tax_line_id)
            LEFT JOIN account_tax_code atc ON (atc.id=ata.tax_code_id)
            where aml.date >= %s and aml.date <= %s and
            ata.tax_code_id in %s and
            aml.tax_line_id IS NOT NULL and ata.tax_code_id IS NOT NULL
            and aml.company_id IN %s
            and am.state IN %s GROUP BY atc.id; """, ((start_date), (end_date), tuple(tax_codes_ids), tuple(company_ids), tuple(state)))
        dict_data = self._cr.dictfetchall()
        for tax_code in dict_data:
            if tax_code.get('id'):
                data = self.browse(tax_code['id'])
                data.tax_amount = tax_code['tax_amount']

    name = fields.Char(string="Tax Case Name", required=True, translate=True)
    code = fields.Char('Case Code', size=64)
    parent_id = fields.Many2one('account.tax.code', 'Parent Code', select=True)
    child_ids = fields.One2many('account.tax.code', 'parent_id', 'Child Codes')
    sequence = fields.Integer('Sequence', help="Determine the display order in the report 'Accounting \ Reporting \ Generic Reporting \ Taxes \ Taxes Report'")
    company_id = fields.Many2one('res.company', 'Company', required=True, default=_default_company)
    tax_amount = fields.Float(compute='_calc_total_tax_amount', string='Tax Total Amount')

    @api.one
    @api.constrains('parent_id')
    def _check_recursion_tax_parent(self):
        level = 100
        while self:
            self = self.parent_id
            if not level:
                raise ValidationError(_('Error! You cannot create recursive accounts.'))
            level -= 1

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=80):
        if not args:
            args = []
        if operator in expression.NEGATIVE_TERM_OPERATORS:
            domain = [('code', operator, name), ('name', operator, name)]
        else:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        ids = self.search(expression.AND([domain, args]), limit=limit)
        return ids.name_get()

    @api.multi
    def name_get(self):
        reads = self.read(['name','code'], load='_classic_write')
        return [(x['id'], (x['code'] and (x['code'] + ' - ') or '') + x['name']) \
                for x in reads]
