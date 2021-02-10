from openerp import models, api, fields, _


class BaseSynchroObj(models.Model):
    _inherit = 'base.synchro.obj'

    @api.model
    def _get_ids(self, obj, dt, domain=None, action=None):
        if action is None:
            action = {}
        if domain is None:
            domain = []
        POOL = self.env[obj]
        result = []
        # Search for records to insert/update
        if dt:
            domain += ['|', ('write_date', '>=', dt), ('create_date', '>=', dt)]
        obj_rec = POOL.search_read(domain)
        for r in obj_rec:
            result.append((r['write_date'] or r['create_date'],
                           r, action.get('action', 'd')))
        return result
