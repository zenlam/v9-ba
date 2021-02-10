odoo.define('br_discount.DB', function (require) {

 "use strict";
    var PosDB = require('point_of_sale.DB');
    PosDB.include({
        init: function (options) {
            // init products item
            this.promotion_items = {};
            this.product_promotion = {};
            this.voucher_items = {};
            this._super(options);
            this.promotion_times = {};
            this.outlet_quotas = {};
            this.user_quotas = {};
        },

        add_items_promotion: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            for (var i = 0, len = items.length; i < len; i++) {
                var promotion = items[i];
                promotion.users_quota = [];
                promotion.outlets_quota = [];
                if (promotion.promotion_category_id instanceof Array)
                    promotion.promotion_category_id = promotion.promotion_category_id[0];
                this.promotion_items[items[i].id] = promotion;
            }
        },

        get_promotion_by_id: function (id) {
            // Should change to false if not found promotion ?
            return this.promotion_items[id] || [];
        },
        get_voucher_promotion_by_id: function(id){
            return this.voucher_items[id] || false;
        },
        add_items_product_promotion: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            for (var i = 0, len = items.length; i < len; i++) {
                var promotion_line = items[i];
                var promotion_id = promotion_line.bundle_promotion_id || promotion_line.product_bundle_promotion_id;
                var promotion = promotion_id && this.promotion_items[promotion_id[0]] || false;
                if(promotion){
                    if(promotion.promotion_lines){
                        promotion.promotion_lines.push(promotion_line);
                    }else{
                        promotion.promotion_lines = [promotion_line];
                    }
                    promotion_line.promotion = promotion;
                }
                this.product_promotion[items[i].id] = promotion_line;
            }
        },

        get_product_promotion_by_id: function (id) {
            return this.product_promotion[id] || [];
        },

        add_items_vouchers: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            for (var i = 0, len = items.length; i < len; i++) {
                var voucher = items[i];
                voucher.users_quota = [];
                voucher.outlets_quota = [];
                if (voucher.promotion_category_id instanceof Array)
                    voucher.promotion_category_id = voucher.promotion_category_id[0];
                if (voucher.voucher_category_id instanceof Array)
                    voucher.voucher_category_id = voucher.voucher_category_id[0];
                this.voucher_items[items[i].id] = voucher;
            }
        },

        //Poor naming ....
        get_voucher_by_id: function (id) {
            return this.voucher_items[id] || false;
        },

        add_items_promotion_times: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            for (var i = 0, len = items.length; i < len; i++) {
                var pro_time = items[i];
                if (pro_time.promotion_category_id instanceof Array)
                    pro_time.promotion_category_id = pro_time.promotion_category_id[0];
                if (pro_time.voucher_category_id instanceof Array)
                    pro_time.voucher_category_id = pro_time.voucher_category_id[0];
                this.promotion_times[items[i].id] = pro_time;
            }
        },

        get_promotion_time_by_id: function (id) {
            return this.promotion_times[id] || [];
        },

        add_items_outlet_quota_ids: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            var line;
            var promotion;
            for (var i = 0, len = items.length; i < len; i++) {
                line = items[i];
                this.outlet_quotas[line.id] = line;
                promotion = this.get_promotion_by_id(line.promotion_id[0]) || this.get_voucher_promotion_by_id(line.promotion_id[0]);
                if(!promotion.outlets_quota){
                    promotion.outlets_quota = [line];
                }else{
                    promotion.outlets_quota.push(line)
                }
                line.promotion = promotion;
            }
        },

        get_outlet_quota_by_id: function (id) {
            return this.outlet_quotas[id] || [];
        },

        add_items_user_quota_ids: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            var line;
            var promotion;
            for (var i = 0, len = items.length; i < len; i++) {
                line = items[i];
                this.user_quotas[line.id] = line;
                promotion = this.get_promotion_by_id(line.promotion_id[0]) || this.get_voucher_promotion_by_id(line.promotion_id[0]);
                if(!promotion.users_quota){
                    promotion.users_quota = [line];
                }else {
                    promotion.users_quota.push(line);
                }
                line.promotion = promotion;
            }
        },

        get_item_user_by_id: function (id) {
            return this.user_quotas[id] || [];
        },



    });
});