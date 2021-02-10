from openerp import models, fields, api, SUPERUSER_ID, _
import br_model


class br_pos_session(br_model.BrModel):
    _inherit = 'pos.session'

    @api.model
    def _get_domain(self, user, domain):
        domain.append(('outlet_id.user_ids', 'in', [user.id]))
        return domain