odoo.define('br_discount.ListView', function (require) {
    "use strict";

    var ListView = require('web.ListView');

    ListView.include({
        /*
        * Inherit and remove Action sidebar for br.voucher.listing model
        */
        render_sidebar: function($node) {
            var self = this;

            this._super.apply(this,arguments);

            if (self.fields_view.model === 'br.voucher.listing' && self.fields_view.name === 'br.voucher.listing.tree') {
                // remove the 'other' sections
                for (var i = 0; i < self.sidebar.sections.length; i++) {

                    if (self.sidebar.sections[i].name === 'other') {
                        self.sidebar.sections.splice(i, 1);
                    }
                }
                // re-render the sidebar to apply changes
                self.sidebar.redraw();
            }
        },
    });
});