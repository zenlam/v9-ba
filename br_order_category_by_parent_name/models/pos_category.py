from openerp.osv import osv, fields
from openerp import api
from openerp.addons.point_of_sale.point_of_sale import pos_category

class br_pos_category(osv.osv):
    _inherit = 'pos.category'

    _columns = {
        'complete_name': fields.function(pos_category._name_get_fnc, type="char", string='Name', store=True),
    }

    _order = 'complete_name'

    @api.multi
    def write(self, vals):
        children = self.env['pos.category'].search([('id', 'child_of', self.id)])
        res = super(br_pos_category, self).write(vals)
        if 'name' in vals:
            self.change_child_name(children)
        elif 'parent_id' in vals:
            self.change_child_name(children)
        return res

    @api.multi
    def change_child_name(self, children):
        if children:
            for c in children:
                c.complete_name = c.name_get()