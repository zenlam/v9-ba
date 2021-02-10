from openerp.osv import osv, fields

class crm_partner(osv.osv_memory):

    _inherit = 'crm.lead2opportunity.partner'

    _columns = {
        'action': fields.selection([
            ('exist', 'Link to an existing customer'),
            ('nothing', 'Do not link to a customer')
        ], 'Related Customer', required=True),
    }
