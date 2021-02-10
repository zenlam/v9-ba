from openerp import models, fields, api, SUPERUSER_ID, _
import br_model

class br_multi_outlet(br_model.BrModel):
    _inherit = 'br_multi_outlet.outlet'

    @api.model
    def create(self, vals):
        users = [self.env.uid]
        if 'user_ids' in vals and vals['user_ids']:
            users += vals['user_ids'][0][2]
        vals.update(user_ids=[[6, 0, list(set(users))]])
        return super(br_multi_outlet, self).create(vals)

    @api.model
    def _get_domain(self, user, domain):
        if self._get_active_model() == 'br_multi_outlet.outlet':
            domain.append(('id', 'in', [x.id for x in user.outlet_ids]))
        return domain
