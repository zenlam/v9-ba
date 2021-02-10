from openerp import api, models, fields, _
from openerp.exceptions import UserError, ValidationError
from datetime import datetime, date
import logging
_logger = logging.getLogger(__name__)


class account_account(models.Model):
    _inherit='account.account'
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if self._context.get('view_all'):
            pass
        else:
            if args:
                args.extend([('type', 'not in', ['view'])])
            else:
                args = [('type', 'not in', ['view'])]
        return super(account_account, self).name_search(name, args=args, operator=operator, limit=limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):

        if self._context.get('view_all'):
            pass
        else:
            if domain:
                domain += [('type', 'not in', ['view'])]
            else:
                domain = [('type', 'not in', ['view'])]
        return super(account_account, self).search_read(domain=domain, fields=fields, offset=offset, limit=limit,
                                                        order=order)


class account_analytic_account(models.Model):
    _inherit='account.analytic.account'

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if self._context.get('view_all_analytic'):
            pass
        else:
            if args:
                args.extend([('internal_type', 'not in', ['view'])])
            else:
                args = [('internal_type', 'not in', ['view'])]
        return super(account_analytic_account, self).name_search(name, args=args, operator=operator, limit=limit)

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        if self._context.get('view_all_analytic'):
            pass
        else:
            if domain:
                domain += [('internal_type', 'not in', ['view'])]
            else:
                domain = [('internal_type', 'not in', ['view'])]
        return super(account_analytic_account, self).search_read(domain=domain, fields=fields, offset=offset,
                                                                 limit=limit, order=order)