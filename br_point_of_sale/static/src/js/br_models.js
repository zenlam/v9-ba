odoo.define('br_point_of_sale.models', function (require) {
    "use strict";
    var models = require('point_of_sale.models');
    var utils = require('web.utils');
    var round_di = utils.round_decimals;
    var parentPrototype = models.PosModel.prototype;
    var parentOrderlinePrototype = models.Orderline.prototype;
    var PaymentlinePrototype = models.Paymentline.prototype;
    var round_pr = utils.round_precision;
    var OrderPrototype = models.Order.prototype;
    var Model = require('web.DataModel');
    var screens = require('point_of_sale.screens');
    models.Order.prototype.UNLIMITED = 9999;

    models.Orderline = models.Orderline.extend({
        initialize: function (attr, options) {
            parentOrderlinePrototype.initialize.call(this, attr, options);
            this.items = [];
            var json = options.json;
            if (json) {
                this.qty = json.qty;
                this.price_unit = json.price_unit;
                this.discount = json.discount;
                this.product_id = json.product_id;
                this.tax_ids = json.tax_ids;
                // Addition values
                this.id = json.id;
                this.product_master_id = json.product_master_id;
                this.is_bundle_item = json.is_bundle_item;
                this.is_flavour_item = json.is_flavour_item;
                this.show_in_cart = json.show_in_cart;
                this.bom_line_id = json.bom_line_id;
                this.bom_quantity = json.bom_quantity;
                this.product_category_id = json.product_category_id;
                this.error = json.error;
                //TruongNN
                this.promotion_id = json.promotion_id;
                this.product_promotion_id = json.product_promotion_id;
                this.discount_amount = json.discount_amount;
                this.rate_promotion = json.rate_promotion;

                //VanNH
                this.bill_type = json.bill_type;
                this.bill_amount = json.bill_amount;
                this.min_bill_apply = json.min_bill_apply;
                this.bill_promotion_ids = json.bill_promotion_ids;
                this.price_flavor = json.price_flavor;
                this.user_promotion = json.user_promotion;
                this.non_sale = json.non_sale;
                this.voucher = json.voucher;
                this.origin_price = json.origin_price;
            } else {
                this.product_master_id = options.hasOwnProperty('product_master_id') ? options.product_master_id : false;
                this.is_bundle_item = options.hasOwnProperty('is_bundle_item') ? options.is_bundle_item : false;
                this.is_flavour_item = options.hasOwnProperty('is_flavour_item') ? options.is_flavour_item : false;
                this.show_in_cart = options.hasOwnProperty('show_in_cart') ? options.show_in_cart : true;
                this.bom_line_id = options.hasOwnProperty('bom_line_id') ? options.bom_line_id : false;
                this.bom_quantity = options.bom_quantity ? parseFloat(options.bom_quantity) : false;
                this.product_category_id = options.product_category_id ? options.product_category_id : false;

                this.promotion_id = options.promotion_id || false;
                this.product_promotion_id = options.product_promotion_id || false;
                this.discount_amount = options.discount_amount || false;
                this.rate_promotion = options.rate_promotion || false;
                this.is_line_discount = options.is_line_discount || false;

                this.bill_type = options.bill_type || false;
                this.bill_amount = options.bill_amount || false;
                this.min_bill_apply = options.min_bill_apply || false;
                this.bill_promotion_ids = options.bill_promotion_ids || [];
                this.price_flavor = options.price_flavor || false;
                this.user_promotion = options.user_promotion || false;
                this.non_sale = options.non_sale || false;
                this.voucher = options.voucher || [];
                this.origin_price = this.is_flavour_item || this.is_line_discount ? 0: this.get_unit_price();
            }
            this.parent_line = options.parent_line;
            this.is_topping_item = options.hasOwnProperty('is_topping_item') ? options.is_topping_item : false;
            this.parent_product_id = options.hasOwnProperty('parent_product_id') ? options.parent_product_id : false;
            this.bom_uom_id = options.bom_uom_id ? parseInt(options.bom_uom_id) : false;
            var product = this.get_product();
            this.product_has_flavours = false;
            if (!_.isEmpty(product)) {
                this.product_has_flavours = !!product.product_recipe_lines.length;
            }

            this.is_bundle_voucher_item = options.hasOwnProperty('is_bundle_voucher_item') ? options.is_bundle_voucher_item : false;

        },
        init_from_JSON: function (json) {
            parentOrderlinePrototype.init_from_JSON.call(this, json);
        },
        export_as_JSON: function () {
            var res = {
                qty: this.get_quantity(),
                price_unit: this.get_unit_price(),
                discount: this.get_discount(),
                product_id: this.get_product().id,
                tax_ids: [[6, false, _.map(this.get_applicable_taxes(), function (tax) {
                    return tax.id;
                })]],
                id: this.id,
                // Addition values
                is_flavour_item: this.is_flavour_item,
                bom_line_id: this.bom_line_id,
                show_in_cart: this.show_in_cart,
                is_bundle_item: this.is_bundle_item || this.is_bundle_voucher_item,
                product_master_id: this.product_master_id,
                pricelist_id: this.pos.config.pricelist_id[0],
                bom_quantity: this.bom_quantity,
                product_category_id: this.product_category_id,
                error: this.error,
                promotion_id: this.promotion_id,
                promotion_line_id: this.promotion_line_id,
                product_promotion_id: this.product_promotion_id,
                discount_amount: this.discount_amount,
                rate_promotion: this.rate_promotion,
                bill_type: this.bill_type,
                bill_amount: this.bill_amount,
                min_bill_apply: this.min_bill_apply,
                bill_promotion_ids: this.bill_promotion_ids,
                price_flavor: this.price_flavor,
                user_promotion: this.user_promotion,
                non_sale: this.non_sale,
                voucher: this.voucher,
                origin_price: this.origin_price
            };
            if (res.bom_quantity) {
                res.total_qty = res.qty * res.bom_quantity;
            }
            return res;
        },
        set_voucher: function (voucher) {
            //Assign voucher for orderline
            this.voucher = voucher;
            this.set({'voucher': this.voucher});
            this.order.trigger('change', this.order);
        },
        //vannh tax fiscal position
        get_applicable_taxes: function () {
            var i;
            // Shenaningans because we need
            // to keep the taxes ordering.
            var taxes_product = this.get_product().taxes_id;
            var self = this;
            var ptaxes_ids = [];
            _(taxes_product).each(function (tax) {
                var tax_after_fiscal = self._map_tax_fiscal_position(self.pos.taxes_by_id[tax]);
                ptaxes_ids.push(tax_after_fiscal);
            })
            var ptaxes_set = {};
            for (i = 0; i < ptaxes_ids.length; i++) {
                ptaxes_set[ptaxes_ids[i].id] = true;
            }
            var taxes = [];
            for (i = 0; i < this.pos.taxes.length; i++) {
                if (ptaxes_set[this.pos.taxes[i].id]) {
                    taxes.push(this.pos.taxes[i]);
                }
            }
            return taxes;
        },
        // Override base function: Base raises exception when tax is undefined
        // because target_tax in fiscal_position is not configured
        compute_all: function (taxes, price_unit, quantity, currency_rounding) {
            var self = this;
            var total_excluded = round_pr(price_unit * quantity, currency_rounding);
            var total_included = total_excluded;
            var base = total_excluded;
            var list_taxes = [];
            if (this.pos.company.tax_calculation_rounding_method == "round_globally") {
                currency_rounding = currency_rounding * 0.00001;
            }
            _(taxes).each(function (tax) {
                tax = self._map_tax_fiscal_position(tax);
                if (tax) {
                    if (tax.amount_type === 'group') {
                        var ret = self.compute_all(tax.children_tax_ids, price_unit, quantity, currency_rounding);
                        total_excluded = ret.total_excluded;
                        base = ret.total_excluded;
                        total_included = ret.total_included;
                        list_taxes = list_taxes.concat(ret.taxes);
                    }
                    else {
                        var tax_amount = self._compute_all(tax, base, quantity);
                        tax_amount = round_pr(tax_amount, currency_rounding);

                        if (tax_amount) {
                            if (tax.price_include) {
                                total_excluded -= tax_amount;
                                base -= tax_amount;
                            }
                            else {
                                total_included += tax_amount;
                            }
                            if (tax.include_base_amount) {
                                base += tax_amount;
                            }
                            var data = {
                                id: tax.id,
                                amount: tax_amount,
                                name: tax.name,
                            };
                            list_taxes.push(data);
                        }
                    }
                }
            });
            return {taxes: list_taxes, total_excluded: total_excluded, total_included: total_included};
        },
        add_item_line: function (line) {
            if (!this.items) {
                this.items = [];
            }
            for (var i = 0; i < this.items.length; i++) {
                if (this.items[i] === line)
                    return;
            }
            this.items.push(line);
            line.parent_line = this;
            this.update_bom_status();
        },
        remove_item_line: function (line) {
            line.parent_line = null;
            for (var i = 0; i < this.items.length; i++) {
                if (this.items[i] == line) {
                    this.items.splice(i, 1);
                    this.update_bom_status();
                    break;
                }
            }
        },
        update_bom_status: function () {
            var product = this.get_product(), capacity = this.get_bom_capacity();
            var miss = false;
            for (var k in capacity) {
                if (this.pos.db.get_bom_lines_by_ids(Number(k))[0]) {
                    if (this.pos.db.get_bom_lines_by_ids(Number(k))[0].hasOwnProperty('is_topping')) {
                        var not_compulsory = this.pos.db.get_bom_lines_by_ids(Number(k))[0].is_topping;
                        if (capacity[k] != 0 && capacity[k] != models.Order.prototype.UNLIMITED && !not_compulsory) {
                            miss = true;
                            break;
                        }
                    }
                }
            }
            if (miss) {
                var bom_line = this.pos.db.get_bom_line_by_line_id(k);
                miss = this.get_product().display_name + '/' + bom_line.name + ' is ' + Math.abs(capacity[k]) + ' units ' + (capacity[k] > 0 ? 'short' : 'over');
            }
            this.set_error_status(miss);

        },
        set_error_status: function (is_error) {
            if (this.error != is_error) {
                this.error = is_error;
                this.trigger('change:status', this);
            }
        },
        br_can_be_merged_with: function (orderline) {
            var self = this;
            if (this.get_product().available_in_pos === false) {
                return self.item_master_can_be_merged_with(orderline);
            } else {
                if (typeof orderline.is_bundle_item != 'undefined' && this.is_bundle_item !== orderline.is_bundle_item) {
                    return false;
                }
                return self.can_be_merged_with(orderline);
            }
        },
        can_be_merged_with: function (orderline) {
            if (this.get_product().id !== orderline.get_product().id || !orderline.parent_line) {
                //only orderline of the same product can be merged
                return false;
            } else if (!this.get_unit() || !this.get_unit().groupable) {
                return false;
            } else if (this.get_product_type() !== orderline.get_product_type()) {
                return false;
            } else if (this.get_discount() > 0) {
                // we don't merge discounted orderlines
                if (this.pos.get('selectedOrder').is_merge_discount == true) {
                    return true;
                } else {
                    return false;
                }
                // } else if (this.get_discount_amount() > 0) {
                //     return false;
            } else if (this.price !== orderline.price) {
                return false;
            } else {
                return true;
            }
        },
        item_master_can_be_merged_with: function (orderline) {
            if (this.get_product().id !== orderline.get_product().id || !orderline.parent_line) {
                //only orderline of the same product can be merged
                return false;
            } else if (this.bom_line_id && this.bom_line_id !== orderline.bom_line_id) {
                return false;
            } else if (this.product_master_id && this.product_master_id !== orderline.product_master_id) {
                return false;
            } else if (this.is_flavour_item && this.is_flavour_item !== orderline.is_flavour_item) {
                return false;
            } else if (this.is_topping_item && this.is_topping_item !== orderline.is_topping_item) {
                return false;
            } else if (this.get_product_type() !== orderline.get_product_type()) {
                return false;
            } else if (this.get_discount() > 0) {
                // we don't merge discounted orderlines
                return false;
            } else if (this.price !== orderline.price) {
                return false;
            } else if (this.parent_line !== orderline.parent_line) {
                return false;
            } else {
                return true;
            }
        },
        get_bom_capacity: function () {
            var product = this.get_product(), capacity = {};
            if (this.product_has_flavours && product.product_recipe_lines.length) {
                var bom = {
                    name: product.display_name,
                    line_ids: this.pos.db.get_bom_lines_by_ids(product.product_recipe_lines)
                };
                //validate bom
                if (bom.line_ids.length > 0) {
                    for (var b = 0; b < bom.line_ids.length; b++) {
                        var bl = bom.line_ids[b];
                        var line_rules = bl.rules;
                        if (line_rules.length > 0) {
                            //if(line_rules.length > 1 && line_rules[0].product_id){
                            if (bl.times == 0) {
                                capacity[bl.id] = models.Order.prototype.UNLIMITED;  // if times is 0, unlimited choice is granted
                            } else {
                                capacity[bl.id] = bl.times * this.get_quantity();
                            }  //}
                        }
                    }
                    if (this.items) {
                        for (var i = 0; i < this.items.length; i++) {
                            var item = this.items[i];
                            if (capacity[item.bom_line_id] != models.Order.prototype.UNLIMITED) {
                                //check quantity, rounding quantity
                                capacity[item.bom_line_id] = parseFloat(capacity[item.bom_line_id] - item.get_quantity()).toFixed(3);
                            }
                        }
                    }
                }
            }
            return capacity;
        },
        export_for_printing: function () {
            var res = parentOrderlinePrototype.export_for_printing.call(this);
            res.product_id = this.get_product().id;
            return res;

        },
        get_taxes_code: function () {
            var self = this,
                order = this.order,
                taxes = this.get_taxes(),
                taxes_code = [];

            taxes.forEach(function (tax) {
                tax = self._map_tax_fiscal_position(tax);
                // console.log(tax);
                if (tax) {
                    var tax_code = order.pos.taxes_by_id[tax['id']].tax_code;
                    if (tax_code)
                        taxes_code.push(tax_code);
                }
            });
            return taxes_code.join(', ')
        },

        get_display_name: function () {
            var ret_name = this.get_product().display_name;
            if (this.get_product().id == this.pos.config.discount_product_id[0] ||
                this.get_product().id == this.pos.config.discount_promotion_bundle_id[0] ||
                this.get_product().id == this.pos.config.discount_promotion_product_id[0]) {
                if (this.promotion_id != false) {
                    return this.pos.db.get_promotion_by_id(this.promotion_id).name != undefined
                        ? this.pos.db.get_promotion_by_id(this.promotion_id).name : this.pos.db.get_voucher_by_id(this.promotion_id).name;
                } else if (this.bill_promotion_ids.length > 0) {
                    for (var j in this.bill_promotion_ids) {
                        var promotion_id = this.bill_promotion_ids[j];
                        var promotion = this.pos.db.get_promotion_by_id(promotion_id) || this.pos.db.get_voucher_by_id(promotion_id);
                        if (promotion.is_hq_voucher) {
                            return promotion.name;
                        }
                    }
                }
            }
            return ret_name;
        }
    });

    // Must place this declaration here because we just add some changes to Orderline model in the above code
    var Orderline = models.Orderline;

    models.Order = models.Order.extend({
        initialize: function (attributes, options) {
            OrderPrototype.initialize.call(this, attributes, options);
            if (this.pos.fiscal_positions.length) {
                this.fiscal_position = this.pos.fiscal_positions[0];
            }
            var order_lines = this.orderlines.models;
            // Add children orderline to their parent
            for (var i = 0; i < order_lines.length; i++) {
                order_lines[i].items = [];
                // Since children orderline is its parent's next orderlines, loop until next parent orderline
                // Note: parent orderlines don't have product_master_id property
                var j = i + 1;
                while (j < order_lines.length && order_lines[j].product_master_id) {
                    order_lines[j].parent_line = order_lines[i];
                    order_lines[i].items.push(order_lines[j]);
                    order_lines[i].update_bom_status();
                    j++;
                }
                i = j - 1;
            }
            this.name = this.pos.outlet.code + this.pos.config.code + " " + this.uid;
            if (!options.json) {
                this.validation_date = undefined;
                // this.is_printed = false;
            } else {
                // this.is_printed = options.json.is_printed;
                this.pos.config.sequence_number = Math.max(this.pos.config.sequence_number + 1, this.pos.config.sequence_number);
                this.validation_date = options.json.validation_date;
            }
            this.invoice_no = this.generate_invoice_no();
            // this.add_paymentline(this.pos.rounding_cashregister)
            this.posDisplay = window.br_socket.POSDisplay('Display Product');
            var start_time = ""
            if (options.json) {
                if (options.json.start_time) {
                    start_time = new Date(options.json.start_time);
                }
            }
            this.start_time = start_time;
            this.time_spend = 0;
            this.third_party_id = '';
            this.current_voucher_code = false;
        },

        initialize_validation_date: function () {
            this.validation_date = new Date();
        },
        generate_unique_id: function () {
            // Generates a public identification number for the order.
            // The generated number must be unique and sequential. They are made 12 digit long
            // to fit into EAN-13 barcodes, should it be needed
            function zero_pad(num, size) {
                var s = "" + num;
                while (s.length < size) {
                    s = "0" + s;
                }
                return s;
            }
            return zero_pad(this.pos.pos_session.id, 5) + '-' +
                zero_pad(window['login_number'], 3) + '-' +
                zero_pad(this.sequence_number, 4) + '-' +
                Date.now(); // It returns the number of milliseconds elapsed since January 1, 1970, 00:00:00 UTC
        },
        get_start_time: function () {
            var self = this;
            return self.start_time;
        },
        get_time_spend: function () {
            var self = this;
            return self.time_spend;
        },
        get_third_party_id: function() {
            var self = this;
            return self.third_party_id;
        },
        get_current_voucher_code: function() {
            var self = this;
            return self.current_voucher_code;
        },
        set_current_voucher_code: function(current_voucher_code) {
            this.current_voucher_code = current_voucher_code;
            this.set({current_voucher_code: current_voucher_code});
        },
        remove_current_voucher_code: function() {
            this.set_current_voucher_code(false);
        },
        set_tip: function (tip) {
            var tip_product = this.pos.db.get_product_by_id(this.pos.config.tip_product_id[0]);
            var lines = this.get_orderlines();
            if (tip_product) {
                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].get_product() === tip_product) {
                        lines[i].set_unit_price(tip);
                        return;
                    }
                }
                this.brAddProduct(tip_product, {
                    quantity: 1,
                    price_flavor: tip,
                    price: tip,
                    product_master_id: tip_product
                });
            }
        },
        br_get_total: function() {
            return round_pr(this.orderlines.reduce((function(sum, orderLine) {
                return sum + orderLine.price;
            }), 0), this.pos.currency.rounding);
        },
        add_rounding_payment: function (cashregister) {
            this.assert_editable();
            var self = this;
            var rounding_paymentline = new models.Paymentline({}, {
                order: this,
                cashregister: cashregister,
                pos: this.pos
            });

            // Search and delete old rounding payment
            // var to_remove = false;
            // _.each(this.paymentlines.models, function (line) {
            //     if (line.cashregister.journal.is_rounding_method) {
            //         to_remove = line;
            //     }
            // });
            //
            // if (to_remove) {
            //     this.remove_paymentline(to_remove);
            // }

            // Add new rounding payment line
            // if (cashregister.journal.type !== 'cash' || this.pos.config.iface_precompute_cash) {
            rounding_paymentline.set_amount(self.br_get_rounding_payment(this.get_due()), 0);
            // }
            if (rounding_paymentline.get_amount()) {
                this.paymentlines.add(rounding_paymentline);
            }
            // Move rounding payment to first element of paymentlines
            if (this.paymentlines.models.length > 0 && !this.paymentlines.models[0].cashregister.journal.is_rounding_method) {
                var len_lines = this.paymentlines.length;
                var tmp = this.paymentlines.models[0];
                this.paymentlines.models[0] = this.paymentlines.models[len_lines - 1];
                this.paymentlines.models[len_lines - 1] = tmp;
            }

            return rounding_paymentline;
            // this.select_paymentline(rounding_paymentline);
        },
        add_orderline: function (line) {
            this.assert_editable();
            if (line)
                if (line.order) {
                    line.order.remove_orderline_when_click_apply(line);//QuangNA
                }
            line.order = this;
            this.orderlines.add(line);
            this.select_orderline(this.get_last_orderline());
        },
        select_orderline: function (line) {
            if (line) {
                var order_lines = this.orderlines.models;
                while (line && !line.show_in_cart) {
                    var prev_line_index = order_lines.indexOf(line) - 1;
                    line = order_lines[prev_line_index];
                }
            }
            OrderPrototype.select_orderline.call(this, line);
            this.trigger('change', this);
            this.trigger('change:selected_orderline', this.selected_orderline);
            // make numpad unclickable when the user select a discount line
            var select = this.selected_orderline;
            if (select) {
                if (select.get_product().id == this.pos.config.discount_product_id[0] ||
                select.get_product().id == this.pos.config.discount_promotion_bundle_id[0] ||
                select.get_product().id == this.pos.config.discount_promotion_product_id[0]) {
                    $('.numpad').css("pointer-events","none").css('opacity',0.5);
                } else {
                    $('.numpad').css("pointer-events","auto").css('opacity',1.0);
                }
            }
        },
        deselect_orderline: function () {
            OrderPrototype.deselect_orderline.call(this);
            this.trigger('change:selected_orderline', this.selected_orderline);
        },
        removePromotionLines: function () {
            // Only call this function when cancel none-sale promotion
            var orderlines = this.orderlines.models;
            var promotion_products = [
                this.pos.config.discount_product_id[0],
                this.pos.config.discount_promotion_bundle_id[0],
                this.pos.config.discount_promotion_product_id[0]
            ];
            for (var i = 0; i < orderlines.length; i++) {
                var l = orderlines[i];
                l.product_promotion_id = false;
                l.promotion_id = false;
                l.user_promotion = false;
                l.bill_promotion_ids = [];
                if (promotion_products.indexOf(l.product.id) != -1) {
                    // If remove bill promotion then remove all line
                    // if(l.product.id == this.pos.config.discount_product_id[0]){
                    this.remove_orderline(l);
                    // }else{
                    //     OrderPrototype.remove_orderline.call(this, l);
                    // }
                }
            }
        },
        removeAllLines: function () {
            var orderlines = this.orderlines.models;
            while (orderlines.length > 0) {
                var l = orderlines[0];
                this.remove_orderline(l);
            }
            this.posDisplay.displayText('HI, I am ' + this.pos.user.name + '!');
        },
        removeAllPaymentLines: function () {
            var paymentLines = this.get_paymentlines();
            while (paymentLines.length > 0) {
                var l = paymentLines[0];
                this.remove_paymentline(l);
            }
        },
        //TODO: Separate promotion logic from this function, this looks like a big poo poo now
        remove_orderline: function (line) {
            var self = this;
            if (!line)
                return;
            var product_promotion_id = line.product_promotion_id ? line.product_promotion_id : 0;
            var remove_voucher = function (vouchers) {
                var to_remove = [];
                //Remove voucher from removed orderline
                for (var i in vouchers) {
                    var voucher_idx = self.use_voucher.indexOf(vouchers[i]);
                    if (voucher_idx != -1) {
                        self.use_voucher.splice(voucher_idx, 1);
                        self.set_voucher(self.use_voucher);
                        to_remove.push(vouchers[i]);
                    }
                }
                //Remove orderlines that applied promotion
                var lines = self.get_orderlines();
                var k = lines.length;
                while (k--) {
                    var l = lines[k];
                    for (var x in to_remove) {
                        self.pos.gui.current_screen.voucher_widget.remove_voucher(to_remove[x]);
                        if (l && l.voucher.indexOf(to_remove[x]) != -1) {
                            self.remove_orderline(l);
                        }
                    }
                }
                var vouchers_new = self.use_voucher;
                // delete the voucher member code information from the order if no voucher
                if (vouchers_new.length == 0) {
                    self.set_voucher_member_code(false);
                }
                if (self.pos.gui.current_screen.order_widget){
                    self.pos.gui.current_screen.order_widget.renderElement();
                }
            };

            if (line.voucher) {
                remove_voucher(line.voucher);
            }
            OrderPrototype.remove_orderline.call(this, line);
            // remove items related to order line
            // be-careful when calling this method in an interation loop
            if (line.items && line.items.length > 0) {
                for (var i = line.items.length - 1; i >= 0; i--) {
                    this.remove_orderline(line.items[i]);
                }
            }
            if (line.parent_line) {
                line.parent_line.remove_item_line(line);
            }

            //check promotion
            var promotion_type = '';
            if (line.promotion_id) {
                var promotion = self.pos.db.promotion_items[line.promotion_id] || self.pos.db.get_voucher_by_id(line.promotion_id);
                if (promotion) {
                    promotion_type = promotion.type_promotion;
                }
            }

            //find all promotion that same product_promotion_line and remove it
            if (product_promotion_id > 0 && promotion_type == self.pos.PROMO_PRODUCT) {
                var orderlines = this.get_orderlines().filter(function (x) {
                    return x.product_promotion_id == product_promotion_id
                });
                for (var i = 0; i < orderlines.length; i++) {
                    var orderline = orderlines[i];
                    if (orderline.voucher) {
                        remove_voucher(orderline.voucher);
                    }
                    OrderPrototype.remove_orderline.call(this, orderline);
                    if (orderline.parent_line) {
                        orderline.parent_line.remove_item_line(orderline);
                    }
                }
                return
            }

            //TruongNN find all lines that same promotion_id and remove it
            var discount_line = self.pos.db.get_product_by_id(self.pos.config.discount_promotion_bundle_id[0]);
            if ((promotion_type == self.pos.PROMO_BUNDLE && line.promotion_id && line.product_promotion_id) || (discount_line && discount_line.id == line.product.id)) {
                var orderlines = this.get_orderlines().filter(function (x) {
                    return x.promotion_id == line.promotion_id
                });
                for (var i = orderlines.length - 1; i >= 0; i--) {
                    if (orderlines[i].voucher) {
                        remove_voucher(orderlines[i].voucher);
                    }
                    OrderPrototype.remove_orderline.call(this, orderlines[i]);
                }
            }
            //GET POS DISPLAY DATA
            var display_price = line.get_display_price();
            var unit_price = display_price / line.get_quantity();
            var product = line.product.display_name;
            var quantity = -line.get_quantity();
            this.posDisplay.displayProduct(product, quantity, unit_price, -display_price);
        },
        remove_orderline_when_click_apply: function (line) {
            OrderPrototype.remove_orderline.call(this, line);
        },

        getSession: function () {
            var self = this;
            var session = self.pos.pos_session.name;
            return session;
        },
        init_from_JSON: function (json) {
            this.validation_date = json.creation_date;
            OrderPrototype.init_from_JSON.apply(this, arguments);
        },
        export_as_JSON: function () {
            var json = OrderPrototype.export_as_JSON.apply(this, arguments);
            json.creation_date = this.validation_date || this.creation_date; // todo: rename creation_date in master
            json.outlet_id = this.pos.config.outlet_id[0];
            json.invoice_no = this.invoice_no;
            // json.is_printed = this.is_printed;
            json.time_spend = this.get_time_spend();
            json.start_time = this.get_start_time();
            json.origin_total = this.get_all_prices(true).total_include;
            json.third_party_id = this.get_third_party_id();
            return json;
        },
        getOrderlineByProduct: function (product, options) {
            var self = this;
            var options = options || {};
            if (!(product instanceof Object)) {
                var product = self.pos.db.get_product_by_id(product);
            }
            if (product.id) {
                var orderlines = self.orderlines.models;
                if (orderlines.length > 0) {
                    for (var i = 0; i < orderlines.length; i++) {
                        if (orderlines[i].product.id === product.id) {
                            if (options.is_bundle_item || orderlines[i].is_bundle_item) {
                                if (orderlines[i].is_bundle_item === options.is_bundle_item) {
                                    return orderlines[i];
                                }
                            } else {
                                return orderlines[i];
                            }
                        }
                    }
                }
            }
            return null;
        },
        loadLineBOM: function (line) {
            // check if product of this line is associated with a BOM
            // implicitly add line that does not need to be chosen

            var product = line.get_product();
            if (product.product_recipe_lines) {
                var bom_lines = this.pos.db.get_bom_lines_by_ids(product.product_recipe_lines);
                if (bom_lines) {
                    for (var j = 0, line_len = bom_lines.length; j < line_len; j++) {
                        var bom_line = bom_lines[j];
                        var line_rules = bom_line.rules;
                        if (line_rules && line_rules.length == 1) {
                            /* Add product to order directly */
                            /* Check flavour exist in cart */
                            var exist_item_line = null;
                            if (line.items) {
                                // technically, this block of code should not be happening
                                // since we won't call this method
                                // on existing line
                                // updating these implicit lines quantity is done via set_quantity method
                                // which check if line is _auto_added
                                for (var i = 0; i < line.items.length; i++) {
                                    var item_line = line.items[i];
                                    if (line_rules[0].product_id) {
                                        if (item_line.get_product().id == line_rules[0].product_id) {
                                            //merge with the item line
                                            exist_item_line = item_line;
                                            exist_item_line.set_quantity(parseInt(bom_line.times) * line.get_quantity());
                                            break;
                                        }
                                    }
                                }
                            }
                            if (!exist_item_line && line_rules[0].product_id && bom_line.is_topping === false) {
                                var price_flavor = 0;
                                var self = this;
                                var obj_price = self.pos.arr_lst_price.filter(function (x) {
                                    return x[0] == self.pos.config.pricelist_id[0] && x[1] == line.product.id && x[3] == line_rules[0].product.id && x[4] == bom_line.id
                                });
                                if (obj_price.length > 0) {
                                    price_flavor = obj_price[0][2];
                                }
                                else {
                                    var obj_price_categ = self.pos.arr_lst_price_categ.filter(function (x) {
                                        return x[0] == self.pos.config.pricelist_id[0] && x[1] == line.product.id && x[3] == bom_line.categ_ids[bom_line.categ_ids.length - 1] && x[4] == bom_line.id
                                    });
                                    if (obj_price_categ.length > 0) {
                                        price_flavor = obj_price_categ[0][2];
                                    }
                                }

                                var item_line = this.addItemForLine(line_rules[0].product, line, {
                                    quantity: parseInt(bom_line.times) * line.get_quantity(),
                                    price: 0,
                                    bom_line_id: bom_line.id,
                                    product_master_id: product.id,
                                    merge: false,
                                    is_flavour_item: true,
                                    show_in_cart: false,
                                    bom_quantity: bom_line.product_qty,
                                    bom_uom_id: bom_line.product_uom,
                                    product_category_id: bom_line.categ_ids[bom_line.categ_ids.length - 1],
                                    price_flavor: price_flavor
                                }, false);
                            }
                        }
                    }
                    line.update_bom_status();
                }
            }
        },
        addItemForLine: function (item, line, options, shouldMerge) {
            shouldMerge = shouldMerge === false ? shouldMerge : true;
            options.parent_line = line;
            var item_line = this._addProduct(item, options, shouldMerge);
        },
        add_product: function (product, options) {
            if (this.pos.get_order().start_time == "") {
                this.pos.get_order().start_time = new Date();
            }
            if (this._printed) {
                this.destroy();
                return this.pos.get_order().add_product(product, options);
            }
            //override base *addProduct* such that
            //there won't be mistaking in calling this function
            return this.brAddProduct(product, options);
        },
        brAddProduct: function (product, options, change_selected_line) {
            var line = this._addProduct(product, options);
            if (line) {
                if (line.limit) {
                    var found = false;
                    for (var r = 0; r < line.limit.related.length; r++) {
                        if (line.limit.related[r] == line) {
                            found = true;
                            break;
                        }
                    }
                    if (!found) {
                        line.limit.related.push(line);
                    }
                }
                var change_selected_line = typeof change_selected_line != 'undefined' ? change_selected_line : true;
                if (change_selected_line === true) {
                    this.select_orderline(line);
                }
                //GET POS DISPLAY DATA
                var display_price = line.get_display_price();
                var unit_price = display_price / line.get_quantity();
                var product = line.product.display_name;
                var quantity = line.get_quantity();
                this.posDisplay.displayProduct(product, quantity, unit_price, display_price);
                return line;

            }
        },

        set_orderline_options: function (line, options) {
            for (var i in options) {
                line[i] = options[i] || false;
            }
        },
        _addProduct: function (product, options) {
            var self = this;
            options = options || {};
            options.pos = this.pos;
            options.order = this;
            options.product = product;
            var quantity = -1;
            var line = new Orderline({}, options);
            // self.set_orderline_options(line, options);
            if (options.quantity !== undefined) {
                quantity = options.quantity;
            }
            if (options.price !== undefined) {
                line.set_unit_price(options.price);
            }

            //Truongnn
            if (options.promotion_line_id !== undefined) {
                line.promotion_line_id = options.promotion_line_id;
            }

            if (quantity > -1) {
                if (line)
                    line.set_quantity(quantity);
            }
            if (options.parent_line) {
                // look for line to merge
                var parent = options.parent_line, productLine = null;
                if (parent.items) {
                    // look for item of the same product
                    for (var i = 0; i < parent.items.length; i++) {
                        if (parent.items[i].item_master_can_be_merged_with(line)) {
                            parent.items[i].merge(line);
                            productLine = parent.items[i];
                            break;
                        }
                    }
                }
                if (!productLine) {
                    // merge product of the same parent
                    var models = this.orderlines.models;
                    for (var i = 0; i < models.length; i++) {
                        if (models[i] == options.parent_line) {
                            this.orderlines.add(line, {at: i + 1});
                            break;
                        }
                    }
                    options.parent_line.add_item_line(line);
                    productLine = line;
                }
                options.parent_line.update_bom_status();
                return productLine;
            } else {
                var last_orderline = this.get_last_orderline();
                if (last_orderline && last_orderline.br_can_be_merged_with(line) && options.merge !== false) {
                    last_orderline.merge(line);
                    this.loadLineBOM(line);
                    return last_orderline;
                } else {
                    this.orderlines.add(line);
                    if (typeof options.is_show_deposit == 'undefined') {
                        this.loadLineBOM(line);
                    }
                    return line;
                }
                // }
            }
        },
        check_error_status: function () {
            var models = this.orderlines.models;
            var errors = [];
            for (var i = 0; i < models.length; i++) {
                var l = models[i];
                l.update_bom_status();
                if (l.error) {
                    errors.push(l.error);
                }
            }
            if (errors.length > 0) {
                return errors;
            }
            return false;
        },
        check_is_promotion: function () {
            return this.is_promotion ? true : false;
        },
        br_get_rounding_payment: function (value) {
            if (isNaN(value)) {
                return 0;
            }
            value = value.toFixed(2);
            var res;
            var last_decimal = parseFloat(value).toFixed(2).slice(-1);
            //Avoid floating point
            last_decimal = parseInt(last_decimal);
            if (last_decimal == 0 || last_decimal == 5) {
                return 0;
            }

            if (1 <= last_decimal && last_decimal <= 2) {
                return last_decimal / 100
            }

            if (6 <= last_decimal && last_decimal <= 7) {
                return (last_decimal - 5) / 100
            }

            if (3 <= last_decimal && last_decimal <= 4) {
                return (last_decimal - 5) / 100
            }

            if (8 <= last_decimal && last_decimal <= 9) {
                return (last_decimal - 10) / 100
            }
        },
        generate_invoice_no: function () {
            return this.pos.outlet.code + this.pos.config.code + " " + this.uid;
        },
        select_paymentline: function (line) {
            if (line !== this.selected_paymentline) {
                if (this.selected_paymentline) {
                    this.selected_paymentline.set_selected(false);
                }
                if (line) {
                    if (!line.cashregister.journal.is_rounding_method && !line.locked) {
                        this.selected_paymentline = line;
                    }
                } else {
                    this.selected_paymentline = line;
                }


                if (this.selected_paymentline) {
                    this.selected_paymentline.set_selected(true);
                }
                this.trigger('change:selected_paymentline', this.selected_paymentline);

            }
        },
        get_menulines: function () {
            var menu_lines = [];
            var orderlines = this.get_orderlines();
            for (var k = 0; k < orderlines.length; k++) {
                var line = orderlines[k];
                if (line.parent_line == undefined) {
                    menu_lines.push(line);
                }
            }
            return menu_lines;
        },
        br_get_all_taxes: function () {
            var order_taxes = [];
            var traveled_taxes = [];
            var taxes = this.pos.taxes;
            var orderlines = this.orderlines.models;
            _(orderlines).each(function (line) {
                var product = line.get_product();
                var product_taxes = [];
                _(product.taxes_id).each(function (el) {
                    product_taxes.push(_.detect(taxes, function (t) {
                        return t.id === el;
                    }));
                });

                _(product_taxes).each(function (tax) {
                    tax = line._map_tax_fiscal_position(tax);
                    _(taxes).each(function (t) {
                        if (t.id === tax.id && traveled_taxes.indexOf(t.id) == -1) {
                            traveled_taxes.push(t.id);
                            order_taxes.push(t);
                        }
                        ;
                    });
                });

            });
            return order_taxes;
        },
        br_get_total_with_tax: function (tax) {
            var total_excluded = 0;
            var taxes = this.pos.taxes;
            var orderlines = this.get_orderlines();
            var all_taxes = [];
            _(orderlines).each(function (orderLine) {
                var product_taxes = [];
                _(orderLine.get_product().taxes_id).each(function (el) {
                    product_taxes.push(_.detect(taxes, function (t) {
                        return t.id === el;
                    }));
                });
                var to_compute_taxes = [];
                _(product_taxes).each(function (pt) {
                    pt = orderLine._map_tax_fiscal_position(pt);
                    if (tax.id == pt.id) {
                        to_compute_taxes.push(pt);
                        if (all_taxes.indexOf(pt) === -1) {
                            all_taxes.push(pt);
                        }
                    }
                });
                if (to_compute_taxes.length > 0) {
                    total_excluded += orderLine.get_unit_price() * orderLine.get_quantity();
                }
            });
            total_excluded = this.compute_all(all_taxes, total_excluded, 1, this.pos.currency.rounding).total_excluded;
            return round_pr(total_excluded, this.pos.currency.rounding);
        },
        br_get_total_tax: function () {
            var order = this;
            var total     = order ? order.get_total_with_tax() : 0;
            var taxes     = order ? total - order.get_total_without_tax() : 0;
            return taxes;
            // var taxes = self.br_get_all_taxes();
            // return round_pr(taxes.reduce(function (sum, tax) {
            //     return sum + self.br_get_tax_amount(tax);
            // }, 0), self.pos.currency.rounding);
        },
        // Override point_of_sale base
        get_all_prices: function (use_origin_price) {
            var self = this;
            var amount_per_taxes = {};
            var tax_amount = 0;
            var total_included = 0;
            var total_excluded = 0;
            var taxes = this.pos.taxes;
            var rounding = self.pos.currency.rounding;
            _.each(self.get_orderlines(), function (line) {
                var product = line.get_product();
                var taxes_ids = product.taxes_id;
                var price = use_origin_price === true ? line.origin_price : line.get_unit_price();
                var price_unit = price * (1.0 - (line.get_discount() / 100.0));
                if (taxes_ids in amount_per_taxes) {
                    amount_per_taxes[taxes_ids] += round_pr(price_unit * line.get_quantity(), rounding);
                } else {
                    amount_per_taxes[taxes_ids] = round_pr(price_unit * line.get_quantity(), rounding);
                }
            });
            _.each(amount_per_taxes, function (amount, tax_ids) {
                tax_ids = tax_ids.split(",");
                var product_taxes = [];
                _(tax_ids).each(function (el) {
                    el = parseInt(el);
                    product_taxes.push(_.detect(taxes, function (t) {
                        return t.id === el;
                    }));
                });
                var prices_tax = self.compute_all(product_taxes, amount, 1, rounding);
                tax_amount += prices_tax['total_included'] - prices_tax['total_excluded'];
                total_excluded += prices_tax['total_excluded'];
                total_included += prices_tax['total_included'];
            });
            return {
                'tax': round_pr(tax_amount, rounding),
                'total_exclude': round_pr(total_excluded, rounding),
                'total_include': round_pr(total_included, rounding),
            };
        },
        get_total_tax: function () {
            return this.get_all_prices().tax;
        },
        get_total_without_tax: function () {
            return this.get_all_prices().total_exclude;
        },
        // Bring this to Order model because we change to calculate tax on whole order, not per order line
        _compute_all: function (tax, base_amount, quantity) {
            if (tax.amount_type === 'fixed') {
                var sign_base_amount = base_amount >= 0 ? 1 : -1;
                return (Math.abs(tax.amount) * sign_base_amount) * quantity;
            }
            if ((tax.amount_type === 'percent' && !tax.price_include) || (tax.amount_type === 'division' && tax.price_include)) {
                return base_amount * tax.amount / 100;
            }
            if (tax.amount_type === 'percent' && tax.price_include) {
                return base_amount - (base_amount / (1 + tax.amount / 100));
            }
            if (tax.amount_type === 'division' && !tax.price_include) {
                return base_amount / (1 - tax.amount / 100) - base_amount;
            }
            return false;
        },
        compute_all: function (taxes, price_unit, quantity, currency_rounding) {
            var self = this;
            var total_excluded = round_pr(price_unit * quantity, currency_rounding);
            var total_included = total_excluded;
            var base = total_excluded;
            var list_taxes = [];
            if (this.pos.company.tax_calculation_rounding_method == "round_globally") {
                currency_rounding = currency_rounding * 0.00001;
            }
            _(taxes).each(function (tax) {
                tax = self._map_tax_fiscal_position(tax);
                if (tax) {
                    if (tax.amount_type === 'group') {
                        var ret = self.compute_all(tax.children_tax_ids, price_unit, quantity, currency_rounding);
                        total_excluded = ret.total_excluded;
                        base = ret.total_excluded;
                        total_included = ret.total_included;
                        list_taxes = list_taxes.concat(ret.taxes);
                    }
                    else {
                        var tax_amount = self._compute_all(tax, base, quantity);
                        tax_amount = round_pr(tax_amount, currency_rounding);

                        if (tax_amount) {
                            if (tax.price_include) {
                                total_excluded -= tax_amount;
                                base -= tax_amount;
                            }
                            else {
                                total_included += tax_amount;
                            }
                            if (tax.include_base_amount) {
                                base += tax_amount;
                            }
                            var data = {
                                id: tax.id,
                                amount: tax_amount,
                                name: tax.name,
                            };
                            list_taxes.push(data);
                        }
                    }
                }
            });
            return {taxes: list_taxes, total_excluded: total_excluded, total_included: total_included};
        },
        _map_tax_fiscal_position: function (tax) {
            var order_fiscal_position = this.fiscal_position;
            if (order_fiscal_position) {
                var mapped_tax = _.find(order_fiscal_position.fiscal_position_taxes_by_id, function (fiscal_position_tax) {
                    return fiscal_position_tax.tax_src_id[0] === tax.id;
                });

                if (mapped_tax) {
                    tax = this.pos.taxes_by_id[mapped_tax.tax_dest_id[0]];
                }
            }

            return tax;
        },
        br_get_tax_amount: function (tax) {
            var total_tax = 0;

            var orderlines = this.orderlines.models;
            var taxes = this.pos.taxes;
            for (var i = 0; i < orderlines.length; i++) {
                var line = orderlines[i];
                var product = line.get_product();
                var product_taxes = [];
                _(product.taxes_id).each(function (el) {
                    product_taxes.push(_.detect(taxes, function (t) {
                        return t.id === el;
                    }));
                });
                _(product_taxes).each(function (pt) {
                    pt = line._map_tax_fiscal_position(pt);
                    if (tax.id == pt.id) {
                        if (tax.price_include === true) {
                            total_tax += round_pr((line.price * line.get_quantity()), line.pos.currency.rounding) / (1 + tax.amount / 100) * (tax.amount / 100)
                        } else {
                            total_tax += round_pr((line.price * line.get_quantity()), line.pos.currency.rounding) * (tax.amount / 100);
                        }
                    }
                })
            }
            //truncate to 2 decimal
            // total_tax = parseFloat(total_tax).toFixed(10).toString().substring(0,4);
            return total_tax;
        },
        is_paid_with_cash: function () {
            return !!this.paymentlines.find(function (pl) {
                return pl.cashregister.journal.type === 'cash' && !pl.cashregister.journal.is_rounding_method;
            });
        },
    });

    models.PosModel = models.PosModel.extend({
        /* Override initialize function */
        initialize: function (session, attribute) {
            parentPrototype.initialize.call(this, session, attribute);
            var self = this,
                original_models = self.models,
                new_models = [];
            self.cashier = self.get_cashier();
            this.outlet = null;
            for (var i = 0; i < original_models.length; i++) {
                if (original_models[i].model == 'product.product') {
                    new_models[i] = {
                        model: 'product.product',
                        fields: ['sequence', 'display_name', 'list_price', 'price', 'pos_categ_id', 'taxes_id', 'barcode',
                            'default_code', 'to_weight', 'uom_id', 'description_sale', 'description',
                            'product_recipe_lines', 'product_tmpl_id', 'is_menu', 'pricelist_item_ids'],
                        order: ['sequence', 'default_code', 'name'],
                        domain: [['sale_ok', '=', true], ['available_in_pos', '=', true], ['is_menu', '=', true]],
                        context: function (self) {
                            return {pricelist: self.pricelist.id, display_default_code: false, load_menu_name: true};
                        },
                        loaded: function (self, products) {
                            self.db.add_products(products);
                        }
                    };
                }
                else if (original_models[i].model == 'pos.category') {
                    new_models[i] = {
                        model: 'pos.category',
                        fields: ['id', 'name', 'parent_id', 'child_id', 'image', 'x_color', 'x_background'],
                        domain: null,
                        order: ['sequence', 'name'],
                        loaded: function (self, categories) {
                            self.db.add_categories(categories);
                        },
                    };
                } else if (original_models[i].model == 'account.fiscal.position') {
                    new_models[i] = {
                        model: 'account.fiscal.position',
                        fields: [],
                        domain: function (self) {
                            return [['id', '=', self.config.fiscal_position_ids[0]]];
                        },
                        loaded: function (self, fiscal_positions) {
                            self.fiscal_positions = fiscal_positions;
                        }
                    }
                } else if (original_models[i].model == 'res.company') {
                    new_models[i] = {
                        model: 'res.company',
                        fields: ['currency_id', 'email', 'website', 'company_registry', 'vat', 'name', 'phone',
                            'partner_id', 'country_id', 'tax_calculation_rounding_method', 'street', 'street2', 'city'
                        ],
                        ids: function (self) {
                            return [self.user.company_id[0]];
                        },
                        loaded: function (self, companies) {
                            self.company = companies[0];
                        },
                    }
                } else if (original_models[i].model == 'account.tax') {
                    new_models[i] = {
                        model: 'account.tax',
                        fields: ['name', 'amount', 'price_include', 'include_base_amount', 'amount_type', 'children_tax_ids', 'tax_code'],
                        domain: null,
                        loaded: function (self, taxes) {
                            self.taxes = taxes;
                            self.taxes_by_id = {};
                            _.each(taxes, function (tax) {
                                self.taxes_by_id[tax.id] = tax;
                            });
                            _.each(self.taxes_by_id, function (tax) {
                                tax.children_tax_ids = _.map(tax.children_tax_ids, function (child_tax_id) {
                                    return self.taxes_by_id[child_tax_id];
                                });
                            });
                        },
                    }
                } else if (original_models[i].model == 'account.journal') {
                    //Add field 'is_rouding_method'
                    new_models[i] = {
                        model: 'account.journal',
                        fields: ['type', 'sequence', 'is_rounding_method', 'edc_terminal', 'is_non_clickable', 'is_required_thirdparty', 'e_wallet_id', 'e_wallet_cimb_code', 'background_colour', 'font_colour'],
                        domain: function (self, tmp) {
                            return [['id', 'in', tmp.journals]];
                        },
                        loaded: function (self, journals) {
                            var i;
                            self.journals = journals;

                            // associate the bank statements with their journals.
                            var cashregisters = self.cashregisters;
                            var ilen = cashregisters.length;
                            for (i = 0; i < ilen; i++) {
                                for (var j = 0, jlen = journals.length; j < jlen; j++) {
                                    if (cashregisters[i].journal_id[0] === journals[j].id) {
                                        cashregisters[i].journal = journals[j];
                                        if (journals[j].is_rounding_method == true) {
                                            self.rounding_cashregister = cashregisters[i];
                                        }
                                    }
                                }
                            }


                            self.cashregisters_by_id = {};
                            for (i = 0; i < self.cashregisters.length; i++) {
                                self.cashregisters_by_id[self.cashregisters[i].id] = self.cashregisters[i];
                            }

                            self.cashregisters = self.cashregisters.sort(function (a, b) {

                                if (a.journal.is_rounding_method == true) {
                                    return 1
                                }
                                // prefer cashregisters to be first in the list
                                if (a.journal.type == "cash" && b.journal.type != "cash") {
                                    return -1;
                                } else if (a.journal.type != "cash" && b.journal.type == "cash") {
                                    return 1;
                                } else {
                                    return a.journal.sequence - b.journal.sequence;
                                }
                            });

                        },
                    }
                } else if (original_models[i].model == 'pos.session') {
                    new_models[i] = {
                        model: 'pos.session',
                        fields: ['id', 'journal_ids','name','user_id','config_id','start_at','stop_at','sequence_number','login_number'],
                        domain: function(self){ return [['state','=','opened'],['user_id','=',session.uid]]; },
                        loaded: function(self,pos_sessions){
                            self.pos_session = pos_sessions[0];
                            self.db.add_session_info(pos_sessions[0]);
                        },
                    }
                }
                else {
                    new_models[i] = original_models[i];
                }
            }
            new_models.push(
                {
                    model: 'br_multi_outlet.outlet',
                    fields: [],
                    ids: function (self) {
                        return [self.config.outlet_id[0]];
                    },
                    loaded: function (self, outlets) {
                        self.outlet = outlets[0];
                        new Model("product.pricelist").call("get_outlet_pricelist", [self.outlet.pricelist_id[0]]).done(function (result) {
                            self.list_category = result;
                        }).fail(function (result) {
                        });
                    }
                },
                {
                    model: 'product.product',
                    order: ['sequence', 'default_code', 'name'],
                    fields: [
                        'sequence', 'display_name', 'list_price', 'price', 'pos_categ_id', 'taxes_id', 'ean13', 'default_code',
                        'to_weight', 'uom_id', 'uos_id', 'uos_coeff', 'mes_type', 'description_sale', 'description',
                        'product_tmpl_id', 'available_in_pos', 'categ_id', 'product_recipe_lines'
                    ],
                    domain: [['is_menu', '=', false]],
                    context: function (self) {
                        return {pricelist: self.pricelist.id, display_default_code: false};
                    },
                    loaded: function (self, items) {
                        self.db.add_items_master(items);
                    }
                }, {
                    model: 'br.menu.name.recipe',
                    fields: [
                        'sequence', 'name', 'times', 'applied_for', 'product_qty', 'is_topping',
                        'categ_ids', 'product_menu_id', 'rule_ids', 'instruction'
                    ],
                    domain: null,
                    context: function (self) {
                        return {
                            'load_rule': true
                        };
                    },
                    loaded: function (self, items) {
                        // preprocess product_group such that it's associated with menu name information
                        for (var i = 0; i < items.length; i++) {
                            var b = items[i];
                            if (b.applied_for == 'product' && b.rules) {
                                var rules = [];
                                for (var r = 0; r < b.rules.length; r++) {
                                    var item = self.db.get_item_master_by_id(b.rules[r].product_id[0]);
                                    if (item && item !== []) {
                                        b.rules[r].product = item;
                                        rules.push(b.rules[r]);
                                    }
                                }
                                b.rules = rules;
                            } else if (b.categ_ids) {
                                var rules = [];
                                var visited = {};
                                for (var j = 0; j < b.categ_ids.length; j++) {
                                    visited[b.categ_ids[j]] = true;
                                }
                                for (var item_id in self.db.order_items) {
                                    var item = self.db.order_items[item_id];
                                    if (visited[item.categ_id[0]]) {
                                        rules.push({
                                            product_id: [
                                                item.id,
                                                item.name,
                                            ],
                                            product_code: item.code,
                                            product_qty: b.product_qty,
                                            product: item,
                                        });
                                    }
                                }
                                b.rules = rules;
                            } else {
                                b.rules = [];
                            }
                        }
                        self.items = items;
                        self.db.add_product_group(items);
                    }
                },
                {
                    model: 'account.fiscal.position',
                    fields: [],
                    loaded: function (self, fiscal_positions) {
                        self.all_fiscal_positions = fiscal_positions;
                        self.db.add_fiscal_positions(fiscal_positions);
                    }
                },
                {
                    model: 'account.fiscal.position.tax',
                    fields: [],
                    domain: function (self) {
                            var fiscal_ids = [];
                            self.all_fiscal_positions.forEach(function (fiscal_position) {
                                fiscal_ids.push(fiscal_position.id)
                            });
                            return [['position_id', 'in', fiscal_ids ]];
                        },
                    loaded: function (self, fiscal_position_taxes) {
                        self.all_fiscal_positions.forEach(function (fiscal_position) {
                            fiscal_position.fiscal_position_taxes_by_id = {};
                            fiscal_position.tax_ids.forEach(function (tax_id) {
                                var fiscal_position_tax = _.find(fiscal_position_taxes, function (fiscal_position_tax) {
                                    return fiscal_position_tax.id === tax_id;
                                });

                                fiscal_position.fiscal_position_taxes_by_id[fiscal_position_tax.id] = fiscal_position_tax;
                            });
                        });
                    }
                }
            );
            self.models = new_models;
        },

        after_load_server_data: function () {
            this.cashier = this.get_cashier();
            this.load_orders();
            this.set_start_order();
            if (this.config.use_proxy) {
                return this.connect_to_proxy();
            }
        },
        get_cashier: function () {
            return this.db.get_cashier() || this.cashier || this.user;
        },

        set_cashier: function (user) {
            this.cashier = user;
            this.db.set_cashier(this.cashier);
        },

        load_server_data: function () {
            // show baskin loader
            this.chrome.loading_server_data = true;
            var self = this;
            var loaded = parentPrototype.load_server_data.apply(this, arguments);
            loaded.then(function () {
                self.chrome.loading_server_data = false;
                self.chrome.done_baskin_progress();
            });
            return loaded;
        },

        br_save_to_server: function (orders, options) {
            var self = this;
            var to_sync_orders = [];
            var done_save_to_server = $.Deferred();
            // Number of orders for each batch
            var BATCH_SIZE = 5;
            var chunks_size = Math.ceil(orders.length / BATCH_SIZE);
            var chunks = [];

            var remove_synced_orders = function (to_remove_orders) {
                _.each(to_remove_orders, function (order_id) {
                    self.db.remove_order(order_id);
                });
                self.set('synch', {state: 'connecting', pending: self.db.get_orders().length});
            };

            var onFailed = function (error, event) {
                console.log(error);
                if (error.code === 200) {    // Business Logic Error, not a connection problem
                    //if warning do not need to display traceback!!
                    if (error.data.exception_type == 'warning') {
                        delete error.data.debug;
                    }

                    // Hide error if already shown before ...
                    if ((!self.get('failed') || options.show_error) && !options.to_invoice) {
                        self.gui.show_popup('error-traceback', {
                            'title': error.data.message,
                            'body': error.data.debug
                        });
                    }
                    self.set('failed', error)
                }
                // prevent an error popup creation by the rpc failure
                // we want the failure to be silent as we send the orders in the background
                event.preventDefault();
                console.error('Failed to send orders:', orders);
                //Should we continue to send remaining order or stop whenever a batch failed ?
                done_save_to_server.reject();
            };
            var onComplete = function (order_ids) {
                console.log(order_ids);
                chunks_size--;
                remove_synced_orders(order_ids);
                if (chunks_size == 0) {
                    done_save_to_server.resolve();
                } else {
                    run();
                }
                return order_ids;
            };

            for (var i = 0; i < chunks_size; i++) {
                //Split orders into BATCH_SIZE order / chunk
                chunks.push(orders.slice(i * BATCH_SIZE, BATCH_SIZE + (i * BATCH_SIZE)))
            }

            var run = function () {
                to_sync_orders = chunks.pop();
                var promise = self.br_create_from_ui(to_sync_orders, options);
                promise.then(onComplete).fail(onFailed);
            };
            run();
            return done_save_to_server;
        },
        br_create_from_ui: function (_orders, options) {
            var timeout = typeof options.timeout === 'number' ? options.timeout : 7500 * _orders.length;
            var posOrderModel = new Model('pos.order');
            return posOrderModel.call('create_from_ui',
                [_.map(_orders, function (order) {
                    order.to_invoice = options.to_invoice || false;
                    return order;
                }), {'check_duplicate_order': true}],
                undefined,
                {
                    shadow: !options.to_invoice,
                    timeout: timeout
                }
            )
        },

        // send an array of orders to the server
        // available options:
        // - timeout: timeout for the rpc call in ms
        // returns a deferred that resolves with the list of
        // server generated ids for the sent orders
        _save_to_server: function (orders, options) {
            if (!orders || !orders.length) {
                var result = $.Deferred();
                result.resolve([]);
                return result;
            }

            options = options || {};

            // var self = this;
            // var timeout = typeof options.timeout === 'number' ? options.timeout : 7500 * orders.length;

            // we try to send the order. shadow prevents a spinner if it takes too long. (unless we are sending an invoice,
            // then we want to notify the user that we are waiting on something )

            for (var i in orders) {
                for (var j in orders[i]['data']) {
                    for (var k in orders[i]['data'].lines) {
                        if (orders[i]['data'].lines[k][2].bom_quantity) {
                            orders[i]['data'].lines[k][2].qty = orders[i]['data'].lines[k][2].qty * orders[i]['data'].lines[k][2].bom_quantity
                        }
                    }
                }
            }
            var self = this;
            // Keep the order ids that are about to be sent to the
            // backend. In between create_from_ui and the success callback
            // new orders may have been added to it.
            var order_ids_to_sync = _.pluck(orders, 'id');

            return self.br_save_to_server(orders, options).then(function () {
                self.set('failed', false);
            }).fail(function () {
            });
        },
        convert_to_lowercase: function(name) {
            return name.toLowerCase();
        },
        check_price_list: function(price_list){
            var self = this;
            var price_list_outlet = self.list_category[self.outlet.pricelist_id[0]];
            for (var i in price_list){
                if(price_list_outlet.indexOf(price_list[i]) >= 0){
                    return true;
                }
            }
            return false;
        },
    });

    // add fields to the payment line model
    models.Paymentline = models.Paymentline.extend({
        initialize: function (attr, options) {
            PaymentlinePrototype.initialize.call(this, attr, options);
            this.approval_no = options.approval_no || false;
            this.terminal_id = options.terminal_id || false;
            this.card_number = options.card_number || false;
            this.card_type = options.card_type || false;
            this.transaction_inv_number = options.transaction_inv_number || false;
            this.transaction_date = options.transaction_date || false;
            this.transaction_time = options.transaction_time || false;
            this.merchant_id = options.merchant_id || false;
            this.acquirer_name = options.acquirer_name || false;
            this.acquirer_code = options.acquirer_code || false;
            this.settlement_batch_number = options.settlement_batch_number || false;
            this.unique_transaction_number = options.unique_transaction_number || false;
        },
        export_as_JSON: function(){
            var json = PaymentlinePrototype.export_as_JSON.call(this);
            json.approval_no = this.approval_no;
            json.terminal_id = this.terminal_id;
            json.card_number = this.card_number;
            json.card_type = this.card_type;
            json.transaction_inv_number = this.transaction_inv_number;
            json.transaction_date = this.transaction_date;
            json.transaction_time = this.transaction_time;
            json.merchant_id = this.merchant_id;
            json.acquirer_name = this.acquirer_name;
            json.acquirer_code = this.acquirer_code;
            json.settlement_batch_number = this.settlement_batch_number;
            json.unique_transaction_number = this.unique_transaction_number;
            return json;
        },
        init_from_JSON: function(json){
            PaymentlinePrototype.init_from_JSON.call(this, json);
            this.approval_no = json.approval_no || false;
            this.terminal_id = json.terminal_id || false;
            this.card_number = json.card_number || false;
            this.card_type = json.card_type || false;
            this.transaction_inv_number = json.transaction_inv_number || false;
            this.transaction_date = json.transaction_date || false;
            this.transaction_time = json.transaction_time || false;
            this.merchant_id = json.merchant_id || false;
            this.acquirer_name = json.acquirer_name || false;
            this.acquirer_code = json.acquirer_code || false;
            this.settlement_batch_number = json.settlement_batch_number || false;
            this.unique_transaction_number = json.unique_transaction_number || false;
        },
        get_masked_card_number: function(){
            var card_number = this.card_number;
            var last_four = card_number.slice(-4);
            var result = '';

            for (var i = (card_number.length)-4; i>0 ; i--){
                result += '*';
            }
            return result + last_four;
        }
    });

    return models
});




