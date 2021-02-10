odoo.define('br_point_of_sale.DB', function (require) {

    "use strict";
    var PosDB = require('point_of_sale.DB');
    PosDB.include({
        init: function (options) {
            // init products item
            this.order_items = {};
            this.product_group = {};
            this.fiscal_positions = {};
            this.current_pos_session = false;
            this._super(options);
            this.limit = 9999999; //unlimited
        },
        add_product_group: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            for (var i = 0, len = items.length; i < len; i++) {
                var group = items[i];
                this.product_group[items[i].id] = group;
            }
        },
        add_items_master: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            for (var i = 0, len = items.length; i < len; i++) {
                var product = items[i];
                if (product.product_tmpl_id instanceof Array)
                    product.product_tmpl_id = product.product_tmpl_id[0];
                this.order_items[items[i].id] = product;
            }
        },
        add_session_info: function (pos_sessions) {
            this.current_pos_session = pos_sessions || false;
        },
        get_item_master_by_id: function (id) {
            return this.order_items[id] || [];
        },
        get_bom_line_by_line_id: function (id) {
            return this.product_group[id] || [];
        },
        get_bom_lines_by_ids: function (ids) {
            if (typeof ids === 'number') {
                ids = [ids];
            }
            var lines = [];
            for (var i = 0, l = ids.length; i < l; i++) {
                lines.push(this.product_group[ids[i]]);
            }
            return lines;
        },
        // Override: loading new product from localStorage
        get_product_by_id: function (id) {
            var product = this.product_by_id[id] ? this.product_by_id[id] : this.order_items[id];
            return product;
        },
        add_fiscal_positions: function(items){
            for (var i = 0, len = items.length; i < len; i++) {
                var group = items[i];
                this.fiscal_positions[items[i].id] = group;
            }
        },
        get_fiscal_position_by_id: function(id){
            return this.fiscal_positions[id];
        },
        set_cashier: function(cashier) {
            // Always update if the user is the same as before
            this.save('cashier', cashier);
        },
        get_cashier: function() {
            if (this.current_pos_session.login_number === 1 ){
                localStorage.removeItem(this.name + '_' + 'cashier');
                return false
            } else{
                return this.load('cashier');
            }
        }
    });
});