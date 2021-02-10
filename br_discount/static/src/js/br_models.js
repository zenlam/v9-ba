odoo.define('br_discount.models', function (require) {
    "use strict";
    var models = require('br_point_of_sale.models');
    var parentPrototype = models.PosModel.prototype;
    var PaymentlinePrototype = models.Paymentline.prototype;
    var parentOrderlinePrototype = models.Orderline.prototype;
    var parentOrderPrototype = models.Order.prototype;
    var br_helper = require('br_discount.helper');
    var Model = require('web.Model');

    models.PosModel = models.PosModel.extend({
        /* Override initialize function */
        initialize: function (session, attribute) {
            parentPrototype.initialize.call(this, session, attribute);
            var self = this;
            /* promotion */
            this.get_list_promotion = [];
            this.arr_promotion_times = [];
            this.pricelist_id = false;
            this.current_outlet = {};
            this.bill_promotion = [];
            this.arr_promotion = [];
            this.order_sequence = 1;
            this.DISCOUNT_PERCENT = 1;
            this.DISCOUNT_AMOUNT = 2;
            this.PROMO_BUNDLE = 3;
            this.PROMO_PRODUCT = 2;
            this.PROMO_BILL = 1;
            this.arr_vouchers = [];
            var new_models = self.models;
            this.arr_promotion_product = [];
            this.arr_lst_price = {};
            this.arr_lst_price_categ = {};
            this.outlet_quota_ids = {};
            this.user_quota_ids = {};

            // Promotion
            var field_query = [
                'name', 'real_name', 'code', 'active', 'start_date', 'end_date',
                'type_promotion', 'image', 'is_all_outlet', 'minimum_spending', 'is_voucher',
                'fiscal_position_ids', 'promotion_category_id', 'product_promotion_ids', 'bundle_promotion_ids',
                'is_apply', 'discount_type', 'discount_amount', 'outlet_ids', 'outlet_quota_reset',
                'is_monday', 'is_tuesday', 'is_wednesday', 'is_thursday', 'is_friday', 'is_saturday', 'is_sunday',
                'recurring', 'bundle_promotion_time_ids', 'bundle_promotion_time_week_ids', 'bundle_promotion_time_month_ids',
                'bundle_promotion_time_year_ids', 'instruction', 'image_medium', 'image_small', 'is_non_sale_trans', 'is_smart_detection', 'user_group_ids',
                'quota_type', 'quota', 'used_quota', 'outlet_quota_lines', 'user_quota_type', 'user_quota',
                'user_quota_reset', 'user_quota_lines', 'company_id', 'is_hq_voucher', 'payment_method'

            ];
            var now = new Date();
            // 2015-04-01 05:49:35
            var dateNow = $.datepicker.formatDate('yy-mm-dd', now);
            new_models.push({
                model: 'br.bundle.promotion',
                fields: field_query,
                domain: [
                    [
                        'start_date',
                        '<=',
                        dateNow
                    ],
                    [
                        'is_voucher',
                        '=',
                        false
                    ],
                    '|',
                    [
                        'end_date',
                        '>=',
                        dateNow
                    ],
                    [
                        'end_date',
                        '=',
                        false
                    ]
                ],
                loaded: function (self, promotions) {
                    if (promotions.length > 0) {
                        self.arr_promotion = promotions;
                        promotions.reduce(function (a, b) {
                            b.quota = Number(b.quota);
                            return b;
                        }, '');
                    } else {
                        self.arr_promotion = [];
                    }
                    self.db.add_items_promotion(promotions);
                }
            });

            new_models.push({
                model: 'br.bundle.promotion.time',
                fields: [
                    'bundle_promotion_id',
                    'id',
                    'date',
                    'day_of_month',
                    'start_hour',
                    'end_hour'
                ],
                domain: null,
                loaded: function (self, promotion_times) {
                    if (promotion_times.length > 0) {
                        self.arr_promotion_times = promotion_times;
                    } else {
                        self.arr_promotion_times = [];
                    }
                    self.db.add_items_promotion_times(promotion_times);
                }
            });

            new_models.push({
                model: 'br.bundle.promotion',
                fields: field_query,
                domain: [
                    [
                        'start_date',
                        '<=',
                        dateNow
                    ],
                    [
                        'is_voucher',
                        '=',
                        true
                    ], '|',
                    [
                        'end_date',
                        '>=',
                        dateNow
                    ],
                    [
                        'end_date',
                        '=',
                        false
                    ]
                ],
                loaded: function (self, promotions) {
                    if (promotions.length > 0) {
                        self.arr_vouchers = promotions;
                    } else {
                        self.arr_vouchers = [];
                    }
                    self.db.add_items_vouchers(promotions);
                }
            });

            new_models.push({
                model: 'br.bundle.promotion.product',
                fields: [],
                domain: null,
                loaded: function (self, promotion_products) {
                    if (promotion_products.length > 0) {
                        self.arr_promotion_product = promotion_products;
                    } else {
                        self.arr_promotion_product = [];
                    }
                    self.db.add_items_product_promotion(promotion_products);
                }
            });

            new_models.push({
                model: 'br.promotion.outlet.quota',
                fields: [],
                domain: function(self){ return ['|', ['promotion_id','in', $.map(self.arr_vouchers, function(x){return x.id;})], ['promotion_id','in', $.map(self.arr_promotion, function(x){return x.id;})]]; },
                loaded: function (self, outlet_quota_ids) {
                    if (outlet_quota_ids.length > 0) {
                        self.outlet_quota_ids = outlet_quota_ids;
                    } else {
                        self.outlet_quota_ids = [];
                    }
                    self.db.add_items_outlet_quota_ids(outlet_quota_ids);
                }
            });

            new_models.push({
                model: 'br.promotion.user.quota',
                fields: [],
                domain: function(self){ return ['|', ['promotion_id','in', $.map(self.arr_vouchers, function(x){return x.id;})], ['promotion_id','in', $.map(self.arr_promotion, function(x){return x.id;})]]; },
                loaded: function (self, user_quota_ids) {
                    if (user_quota_ids.length > 0) {
                        self.user_quota_ids = user_quota_ids;
                    } else {
                        self.user_quota_ids = [];
                    }
                    self.db.add_items_user_quota_ids(user_quota_ids);
                }
            });

            /*  End Promotion  */

            self.models = new_models;
            new Model("product.pricelist").call("get_ls_price",
                [])
                .done(function (result) {
                    self.arr_lst_price = result;
                })
                .fail(function (result) {
                });

            new Model("product.pricelist").call("get_ls_price_categ",
                [])
                .done(function (result) {
                    self.arr_lst_price_categ = result;
                })
                .fail(function (result) {
                });

        }
    });

    models.Paymentline = models.Paymentline.extend({
        initialize: function (attr, options) {
            PaymentlinePrototype.initialize.call(this, attr, options);
            this.voucher_code = options.voucher_code || false;
            this.unredeem_value = options.unredeem_value || 0;
            this.is_payment_rounding = options.is_payment_rounding || false;
            if (options) {
                this.locked = options.locked || false;
            } else {
                this.locked = false;
            }
        },
        export_as_JSON: function(){
            var json = PaymentlinePrototype.export_as_JSON.call(this);
            json.voucher_code = this.voucher_code;
            json.unredeem_value = this.unredeem_value;
            json.is_payment_rounding = this.is_payment_rounding;
            return json;
        },
        init_from_JSON: function(json){
            PaymentlinePrototype.init_from_JSON.call(this, json);
            this.voucher_code = json.voucher_code || false;
            this.unredeem_value = json.unredeem_value || 0;
            this.is_payment_rounding = json.is_payment_rounding || false;
        }
    });

    models.Order = models.Order.extend({
        initialize: function (attr, options) {
            parentOrderPrototype.initialize.call(this, attr, options);
            var self = this;
            // Add helper ...
            self.helper = new br_helper({pos: self.pos});
            /* bill amount */
            if (options.json && options.json.use_voucher) {
                this.use_voucher = options.json.use_voucher;
                this.discount_payment = options.json.discount_payment;
            } else {
                if (options.use_voucher) {
                    this.use_voucher = options.use_voucher;
                    this.discount_payment = options.discount_payment;
                } else {
                    this.use_voucher = [];
                    this.discount_payment = {};
                }
            }
            this.note = "";
        },

        addItemForLine: function(item, line, options, shouldMerge){
            parentOrderPrototype.addItemForLine.call(this, item, line, options, shouldMerge);
            this.helper.update_line_bill_promotion();
        },
        export_as_JSON: function () {
            var json = parentOrderPrototype.export_as_JSON.apply(this, arguments);
            json.use_voucher = this.use_voucher;
            json.discount_payment = this.discount_payment;
            json.note = this.note;
            return json;
        },
        set_discount_payment: function (voucher, val) {
            if(voucher in this.discount_payment){
                this.discount_payment[voucher]['amount'] += val['amount'];
            }else {
                this.discount_payment[voucher] = val;
            }
        },
        set_voucher: function (voucher) {
            this.use_voucher = voucher;
            this.set({use_voucher: voucher});
            this.trigger('change', this);
        },
        get_cashregister_by_journal: function (journal_id) {
            //Map journal id with bank statement
            for (var i = 0; i < this.pos.cashregisters.length; i++) {
                if (this.pos.cashregisters[i].journal_id[0] === journal_id) {
                    return this.pos.cashregisters[i];
                }
            }
            return false;
        },
        finalize: function(){
            this.update_quota();
            parentOrderPrototype.finalize.apply(this, arguments);
        },
        update_quota: function(){
            var self = this;
            var get_promotion = function(promotion_id){
                return self.pos.db.get_promotion_by_id(promotion_id) || self.pos.db.get_voucher_promotion_by_id(promotion_id) || false;
            };

            var order_promotions = {};
            var orderlines = this.get_orderlines();
            var i;
            var promotion, orderline;
            // Get all promotion need to be updated
            for(i in orderlines){
                orderline = orderlines[i];
                // if (!orderline.parent_line)
                //     continue;
                promotion = get_promotion(orderline.promotion_id);
                if(promotion && (promotion.quota_type || promotion.user_quota_type)){
                    if(!(promotion.id in order_promotions)){
                        order_promotions[promotion.id] = {'amount': orderline.origin_price, 'quantity': orderline.rate_promotion, "user_id": parseInt(orderline.user_promotion)}
                    }else{
                        if(orderline.parent_line == undefined){
                            order_promotions[promotion.id]['amount'] += orderline.origin_price;
                        }
                    }
                }
            }

            for(var promotion_id in order_promotions){
                promotion = get_promotion(promotion_id);
                var qty = order_promotions[promotion_id].quantity;
                if(promotion.quota_type){
                    // Update outlet quota
                    var outlet_id = this.pos.config.outlet_id[0];
                    if(promotion.quota_type == 'individual'){
                        var outlet_quota_line = promotion.outlets_quota.filter(function(line){return line.outlet_id[0] == outlet_id});
                        outlet_quota_line[0].used_promotion += qty;
                    }else if (promotion.quota_type == 'global'){
                        promotion.used_quota += qty;
                    }
                }else if (promotion.user_quota_type){
                    // Update user quota
                    var user_id =order_promotions[promotion_id].user_id;
                    var user_quota_line = promotion.users_quota.filter(function(line){return line.user_id[0] == user_id});
                    if(promotion.user_quota_type == 'quantity'){
                        user_quota_line[0].used_quota += qty;
                    }else if(promotion.user_quota_type == 'amount'){
                        user_quota_line[0].used_quota += order_promotions[promotion_id].amount;
                    }
                }
            }
        },
    });


    var screens = require('point_of_sale.screens');

    // Override OrderWidget
    screens.OrderWidget.include({
        set_value: function (val) {
            var self = this;
            var order = this.pos.get_order(), order_line = order.get_selected_orderline();
            if (order_line) {
                // if (order_line.price < 0 || (val == "" && (self.pos.config.discount_product_id[0] != order_line.product_id))) {
                if (order_line.price < 0 || (val == "")) {
                    val = 'remove';
                }

                if (val != 'remove' && this.numpad_state.get('mode') == 'quantity') {
                    if (order_line.parent_line && order_line.bom_line_id) {
                        var quant = parseFloat(val) || 0;
                        var bomLine = self.pos.db.get_bom_line_by_line_id(order_line.bom_line_id);
                        if (bomLine) {
                            if (quant > bomLine.times) {
                                this.numpad_state.resetValue();
                                self.error('Hey dude, you can\'t have any more ' + bomLine.name);
                                return;
                            }
                        }
                    }
                }

                // when click numpad add new lines instead of set quantity
                var quantity = parseInt(val);
                var is_applying_promo = $('.breadcrumb-button-apply').is(':visible');
                if (!order_line.parent_line && !isNaN(quantity) && quantity) {
                    if (this.numpad_state.get('mode') == 'quantity') {
                        if (quantity > 1) {
                            quantity = quantity - 1;
                        }
                        for (var i = 0; i < quantity; i++) {
                            var final_promotion_id = order_line.promotion_id;
                            var final_promotion_line_id = order_line.promotion_line_id;
                            // if the promotion is a voucher promotion,
                            // then don't have to populate the promotion to the
                            // new line
                            if (final_promotion_id in this.pos.db.voucher_items){
                                final_promotion_id = false;
                                final_promotion_line_id = false;
                            }
                            var new_order_line = order.add_product(order_line.product, {promotion__id: final_promotion_id, promotion_line_id: final_promotion_line_id});
                            for (var j = 0; j < order_line.items.length; j++) {
                                var item = $.extend(true, {}, order_line.items[j]);
                                item.parent_line = new_order_line;
                                if(!is_applying_promo){
                                    item.promotion_id = false;
                                    item.product_promotion_id = false;
                                    item.discount_amount = false;
                                    item.rate_promotion = false;
                                    item.is_line_discount = false;
                                }
                                if (item.show_in_cart === true) {
                                    order.addItemForLine(item.product, new_order_line, item, false);
                                }
                            }
                        }
                    }
                } else {
                    this._super(val);
                    if (order_line.parent_line) {
                        order_line.parent_line.update_bom_status();
                    }
                }
                 //Begin Vannh xu ly bill promotion
                self.helper = new br_helper({pos: self.pos});
                self.helper.update_line_bill_promotion();
                //End Vannh xu ly bill promotion
            }
        }
    });

    models.Orderline.prototype._map_tax_fiscal_position = function (tax) {
        var current_order = this.pos.get_order(),
            order_fiscal_position;
        order_fiscal_position = current_order && current_order.fiscal_position;

        var promotion_id = this.promotion_id || this.bill_promotion_ids.length > 0 && this.bill_promotion_ids[0] || false,
            promotion = this.pos.db.get_voucher_promotion_by_id(promotion_id) || this.pos.db.get_promotion_by_id(promotion_id);
        if (promotion.id) {
            var fiscal_position_id = promotion.fiscal_position_ids[0];
            order_fiscal_position = this.pos.db.get_fiscal_position_by_id(fiscal_position_id);
        }

        if (order_fiscal_position) {
            var mapped_tax = _.find(order_fiscal_position.fiscal_position_taxes_by_id, function (fiscal_position_tax) {
                return fiscal_position_tax.tax_src_id[0] === tax.id;
            });

            if (mapped_tax) {
                if (mapped_tax.tax_dest_id) {
                    tax = this.pos.taxes_by_id[mapped_tax.tax_dest_id[0]];
                }
                else {
                    tax = false;
                }

            }
        }

        return tax;
    }
});
