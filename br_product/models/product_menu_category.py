# --*-- coding: utf-8 --*--
from openerp import fields, api, models, _
from openerp.osv import expression, osv

class br_menu_category(models.Model):
    _name = 'br.menu.category'

    @api.multi
    @api.depends('name', 'parent_id')
    def name_get(self):
        result = []
        for r in self:
            names = [r.name]
            pcat = r.parent_id
            while pcat:
                names.append(pcat.name)
                pcat = pcat.parent_id
            r.complete_name = ' / '.join(reversed(names))
            result.append((r.id, ' / '.join(reversed(names))))
        return result

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if not context:
            context = {}
        if name:
            # Be sure name_search is symetric to name_get
            categories = name.split(' / ')
            parents = list(categories)
            child = parents.pop()
            domain = [('name', operator, child)]
            if parents:
                names_ids = self.name_search(cr, uid, ' / '.join(parents), args=args, operator='ilike', context=context, limit=limit)
                category_ids = [name_id[0] for name_id in names_ids]
                if operator in expression.NEGATIVE_TERM_OPERATORS:
                    category_ids = self.search(cr, uid, [('id', 'not in', category_ids)])
                    domain = expression.OR([[('parent_id', 'in', category_ids)], domain])
                else:
                    domain = expression.AND([[('parent_id', 'in', category_ids)], domain])
                for i in range(1, len(categories)):
                    domain = [[('name', operator, ' / '.join(categories[-1 - i:]))], domain]
                    if operator in expression.NEGATIVE_TERM_OPERATORS:
                        domain = expression.AND(domain)
                    else:
                        domain = expression.OR(domain)
            ids = self.search(cr, uid, expression.AND([domain, args]), limit=limit, context=context)
        else:
            ids = self.search(cr, uid, args, limit=limit, context=context)
        return self.name_get(cr, uid, ids, context)

    @api.multi
    def _name_get_fnc(self):
        return self.name_get()

    name = fields.Char(string="Category Name", size=128)
    sequence = fields.Integer(string="Sequence")
    parent_id = fields.Many2one(comodel_name="br.menu.category", string="Parent Category", ondelete='restrict')
    complete_name = fields.Char(string=_("Complete Name"), compute='name_get', store=True)

    _parent_name = "parent_id"

    _constraints = [
        (osv.osv._check_recursion, 'Error ! You cannot create recursive categories.', ['parent_id'])
    ]

    @api.multi
    def write(self, vals):
        children = self.env['br.menu.category'].search([('id', 'child_of', self.id)])
        res = super(br_menu_category, self).write(vals)
        if 'name' in vals:
                self.change_child_name(children)
        elif 'parent_id' in vals:
                self.change_child_name(children)
        return res

    @api.multi
    def change_child_name(self, children):
        if children:
            for c in children:
                c.complete_name = c.name_get()[0][1]
