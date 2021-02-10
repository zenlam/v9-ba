from openerp import models, fields, api, SUPERUSER_ID, _


class BrModel(models.Model):
    _register = False

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if SUPERUSER_ID != self.env.uid:
            user = self.env['res.users'].browse(self.env.uid)
            args = self._get_domain(user, args)
        return super(BrModel, self)._search(args, offset=offset, limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if SUPERUSER_ID != self.env.uid:
            user = self.env['res.users'].browse(self.env.uid)
            domain = self._get_domain(user, domain)
        return super(BrModel, self).read_group(domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby, lazy=lazy)

    # @api.model
    def _get_domain(self, user, domain):
        return domain

    def _get_active_model(self):
        c = self.env.context
        active_model = c.get('active_model', False) or c.get('params', False) and c['params'].get('active_model')
        if not active_model:
            action_id = c.get('params', False) and c['params'].get('action', False)
            if action_id:
                active_model = self.env['ir.actions.act_window'].browse(action_id).res_model
        return active_model


