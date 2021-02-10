/**
 * Created by vannh on 25/08/2016.
 */
// Smelly code gonna smell
odoo.define('br_discount.helper', function (require) {
    var Model = require('web.Model');
    var core = require('web.core');
    // var screens = require('point_of_sale.screens');

    var QWeb = core.qweb;
    var _t = core._t;
    var Backbone = window.Backbone;
    var Recurring = Object.freeze({WEEK: 1, MONTH: 2, YEAR: 3});
    // var paymentScreenProto = screens.PaymentScreenWidget.prototype;
    /**
     * Baskin Robbin Widget helper class
     */
    'use strict'

    var PromotionHelper = Backbone.Model.extend({
        initialize: function (attributes) {
            Backbone.Model.prototype.initialize.apply(this, arguments);
            this.pos = attributes.pos;
        },

        check_outlet_for_promotion: function (object, outlet_id) {
            var self = this;
            var check = false;
            if (object.is_all_outlet) {
                check = true;
            }
            else {
                var outlet_ids = object.outlet_quota_lines;
                for (var i = 0; i < outlet_ids.length; i++) {
                    if (self.pos.db.get_outlet_quota_by_id(outlet_ids[i]).outlet_id[0] == outlet_id) {
                        check = true;
                        break;
                    }
                }
            }
            return check;
        },

        /** Load list promotions by type; type=0 if you want to get all*/
        get_list_promotion: function (type) {
            var self = this;
            var info_promotion = [];
            var outlet_id = self.pos.config.outlet_id[0] > 0 ? self.pos.config.outlet_id[0] : 0;
            var arr_promotion = (self.pos.arr_promotion.length > 0) ? self.pos.arr_promotion : [];

            if (arr_promotion.length > 0) {
                for (var i = 0; i < arr_promotion.length; i++) {
                    var check_outlet = self.check_outlet_for_promotion(arr_promotion[i], outlet_id);
                    if (check_outlet) {
                        var check_time = self.check_time_for_promotion(arr_promotion[i], type);

                        if (check_time && (type === 0 || arr_promotion[i].type_promotion == type)) {
                            // to do something ...
                            var obj_promotion = arr_promotion[i];
                            info_promotion.push(obj_promotion);
                        }
                    }
                }
            }
            return info_promotion;
        },

        /** type=0 if you want to get all --Vannh update*/
        check_time_for_promotion: function (object, type_promotion) {
            var self = this;
            var check = false;
            var now = new Date();
            var n = now.getDay();
            if (object.recurring == '') {
                check = true;
            }
            if (object.recurring == Recurring.WEEK) {
                var arr_weekday = [object.is_sunday == true ? 0 : 8,
                    object.is_monday == true ? 1 : 8,
                    object.is_tuesday == true ? 2 : 8,
                    object.is_wednesday == true ? 3 : 8,
                    object.is_thursday == true ? 4 : 8,
                    object.is_friday == true ? 5 : 8,
                    object.is_saturday == true ? 6 : 8
                ];
                if (arr_weekday.indexOf(n) >= 0) {
                    check = true;
                }
            }// recurring by week
            if (object.recurring == Recurring.MONTH) {
                var ls_times = object.bundle_promotion_time_month_ids;
                for (var i = 0; i < ls_times.length; i++) {
                    var promo_datetime = self.pos.db.get_promotion_time_by_id(ls_times[i]);
                    if (now.getDate() == promo_datetime.day_of_month) {
                        check = true;
                    }
                }
            }// recurring by month
             //Recurring by year
            if (object.recurring == Recurring.YEAR) {
                var ls_times = object.bundle_promotion_time_year_ids;
                for (var i = 0; i < ls_times.length; i++) {
                    var pro_datetime = self.pos.db.get_promotion_time_by_id(ls_times[i]);
                    var pro_date = pro_datetime.date;
                    if (pro_date != false) {
                        // var str_cur_date = (parseInt(now.getMonth())+1) < 10 ? '0' + (parseInt(now.getMonth())+1).toString() : (parseInt(now.getMonth())+1).toString()+'-'+(now.getDate() < 10 ? '0' +now.getDate():now.getDate());
                        var str_cur_date = $.datepicker.formatDate('mm-dd', now);
                        var str_pro_date = pro_date.substr(5);
                        // (pro_date.getMonth() < 10 ? '0' + (parseInt(pro_date.getMonth())+1).toString() : (parseInt(pro_date.getMonth())+1).toString())+'-'+(pro_date.getDate() < 10 ? '0' +pro_date.getDate():pro_date.getDate());
                        if (str_cur_date == str_pro_date) {
                            check = true;
                        }
                    }

                }
            } //by year
            return check;
        },

        get_users_for_promotion: function (promotion) {
            var ls_user = [];
            var self = this;
            for (var i = 0; i < promotion.user_quota_lines.length; i++) {
                ls_user.push(self.pos.db.get_item_user_by_id(promotion.user_quota_lines[i]).user_id);
            }
            return ls_user;
        },
        update_quota: function(promotion, quota, user_id){
            if(promotion.quota_type){
                // Update outlet quota
                var outlet_id = this.pos.config.outlet_id[0];
                if(promotion.quota_type == 'individual'){
                    var outlet_quota_line = promotion.outlets_quota.filter(function(line){return line.outlet_id[0] == outlet_id});
                    outlet_quota_line[0].used_promotion = quota;
                }else if (promotion.quota_type == 'global'){
                    promotion.used_quota = quota;
                }
            }else if (promotion.user_quota_type){
                // Update user quota
                var user_quota_line = promotion.users_quota.filter(function(line){return line.user_id[0] == user_id});
                if(user_quota_line.length > 0){
                    user_quota_line[0].used_quota = quota
                }
            }
        },
        check_login: function (user, password) {
            var self = this;
            var promise = $.Deferred();
            new Model('res.users').call('pos_check_login', [user, password]).done(function (result) {
                if (result == false || password.length == 0) {
                    self.pos.gui.show_popup('error', {
                        title: _t('Invalid Login'),
                        body: _t("Invalid username or password!"),
                    });
                    promise.reject();
                }
                promise.resolve(result);
            }).fail(function (response, event) {
                event.preventDefault();
                self.pos.gui.show_popup('error', {
                    title: _t('Invalid Login'),
                    body: _t("Invalid username or password!")
                });
                promise.reject();
            });
            return promise;
        },
        check_promotion_quota: function (parameters, onSuccess, onFail, options, context) {
            /*
             When order with quota info is sent to server there might be a slightly delay (eg: internet connection,...)
             that make the quota on promotion isn't updated at the time system check quota limit for the new order
             which lead to exceeded quota is allowed, so we check on front-end first then double check in backend to
             make sure quota is updated correctly
             * parameters: [outlet_id, user_id, promotion_id]
             * options: {...}
             * context: {...}
             * onSuccess: function(){...}
             * onFail: function(){....}
             * */
            var self = this;
            var opts = options || {timeout: 3000};
            var promise = $.Deferred();
            var outlet_id = parameters[0], user_id = parseInt(parameters[1]), promotion_id = parameters[2];
            var promotion = self.pos.db.get_promotion_by_id(promotion_id);
            if(promotion.length == 0){
                promotion = self.pos.db.get_voucher_promotion_by_id(promotion_id);
            }
            if(!promotion){
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    title: _t('Invalid Discount'),
                    body: _t("Unrecognized promotion, please contact IT support !")
                });
                return promise.reject();
            }
            var check_quota = self.check_promotion_quota_frontend(outlet_id, user_id, promotion);
            if (!check_quota) {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    title: _t('Invalid Discount'),
                    body: _t("Exceeded quota limit, discount is not applicable!"),
                });
                return promise.reject();
            } else {
                var ajax = new Model('br.bundle.promotion').call('get_rate_outlet_user_quota', parameters, context, opts);
                ajax.done(function (result) {
                    if (result[0] == false) {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        self.pos.gui.show_popup('error', {
                            title: _t('Invalid Discount'),
                            body: _t("Exceeded quota limit, discount is not applicable!")
                        });
                    }
                    self.update_quota(promotion, result[3], user_id);
                    if (onSuccess) {
                        onSuccess(result);
                    }
                    promise.resolve(result);
                });

                ajax.fail(function (response, event) {
                    event.preventDefault();
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    self.pos.gui.show_popup('error', {
                        title: _t('Warning'),
                        body: _t("Connection problem, can not apply discount")
                    });
                    if (onFail) {
                        onFail(response, event);
                    }
                    promise.reject(response, event);
                });
            }
            return promise;
        },

        check_promotion_quota_frontend: function (outlet_id, user_id, promotion) {
            // Check if promotion's quota is valid
            var self = this;
            var quota_type = promotion.quota_type;
            var used_quota = 1;
            var promotion_quota = 0;
            if ((!quota_type || promotion.quota == 0) && (promotion.users_quota.length == 0 || promotion.user_quota == 0)) {
                return true;
            }
            else if (quota_type == 'individual') {
                var outlet_quota_line = promotion.outlets_quota.filter(function (line) {
                    return line.outlet_id[0] == outlet_id
                });
                if(outlet_quota_line.length > 0){
                    used_quota = outlet_quota_line[0].used_quota;
                    promotion_quota = promotion.quota;
                }else{
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    self.pos.gui.show_popup('error', {
                        title: _t('Invalid Discount'),
                        body: _t("Can't find outlet to apply quota, please contact IT support!")
                    });
                    return false;
                }
            }

            else if (quota_type == 'global') {
                used_quota = promotion.used_quota;
                promotion_quota = promotion.quota;
            }
            else {
                var user_quota_type = promotion.user_quota_type;
                if (user_quota_type == 'quantity' || user_quota_type == 'amount') {
                    var user_quota_line = promotion.users_quota.filter(function (line) {
                        return line.user_id[0] == user_id
                    });
                    if (user_quota_line.length > 0) {
                        used_quota = user_quota_line[0].used_quota;
                        promotion_quota = promotion.user_quota;
                    }else{
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        self.pos.gui.show_popup('error', {
                            title: _t('Invalid Discount'),
                            body: _t("Can't find user to apply quota, please contact IT support!")
                        });
                        return false;
                    }
                }
            }
            return used_quota <= promotion_quota;
        },

        /*Begin Vannh Get Bill Promotion */
        get_bill_promotion: function () {
            var self = this;
            var current_outlet = self.pos.current_outlet ? self.pos.current_outlet : 0;
            var arr_promotion = self.get_list_promotion(self.pos.PROMO_BILL);
            var order = self.pos.get_order();
            var total = order ? order.get_total_with_tax().toFixed(2) : 0;
            var bill_promotion = [];

            for (var i = 0; i < arr_promotion.length; i++) {
                var times_promotion = [];
                var times_ids = [];
                if (arr_promotion[i].is_smart_detection == false) {
                    continue;
                }
                if (arr_promotion[i].recurring == Recurring.WEEK) {
                    times_ids.push(arr_promotion[i].bundle_promotion_time_week_ids);
                } //by week
                if (arr_promotion[i].recurring == Recurring.MONTH) {
                    var ls_times = arr_promotion[i].bundle_promotion_time_month_ids;
                    var date = new Date;
                    var ls_times_new = [];
                    for (var iindex = 0; iindex < ls_times.length; iindex++) {
                        if (date.getDate() == self.pos.db.get_promotion_time_by_id(ls_times[iindex]).day_of_month) {
                            ls_times_new.push(ls_times[iindex]);
                        }
                    }
                    times_ids.push(ls_times_new);

                } //by month
                if (arr_promotion[i].recurring == Recurring.YEAR) {
                    times_ids.push(arr_promotion[i].bundle_promotion_time_year_ids);
                } //by year

                // if (times_ids.length >0) {
                //     // times_promotion = self.pos.arr_promotion_times.filter(function(x) {return times_ids[0].indexOf(x.id) != -1 });
                //     for (var i_pro = 0; i_pro < times_ids.length; i_pro++) {
                //         times_promotion.push(self.pos.db.get_promotion_time_by_id(times_ids[i_pro]));
                //     }
                // }
                if (times_ids.length > 0 && times_ids[0].length > 0) {
                    for (var i_pro = 0; i_pro < times_ids[0].length; i_pro++) {
                        times_promotion.push(self.pos.db.get_promotion_time_by_id(times_ids[0][i_pro]));
                    }
                }
                var check_times = self.check_times_promotion(times_promotion, arr_promotion[i]);
                if (check_times == true || times_ids.length == 0) {
                    if (total >= arr_promotion[i].minimum_spending) {
                        if (self.apply_with_other_promotion(arr_promotion[i].is_apply) == true) {
                            bill_promotion.push(arr_promotion[i]);
                        }
                    }
                }
            }
            return bill_promotion;
        },

        check_time_bill_promotion: function (promotion) {
            var self = this;
            var msg_available = [false, ""];
            var order = self.pos.get_order();
            var times_promotion = [];
            var times_ids = [];
            if (promotion.recurring == Recurring.WEEK) {
                times_ids.push(promotion.bundle_promotion_time_week_ids);
            } //by week
            if (promotion.recurring == Recurring.MONTH) {
                var ls_times = promotion.bundle_promotion_time_month_ids;
                var date = new Date;
                var ls_times_new = [];
                for (var i = 0; i < ls_times.length; i++) {
                    if (date.getDate() == self.pos.db.get_promotion_time_by_id(ls_times[i]).day_of_month) {
                        ls_times_new.push(ls_times[i]);
                    }
                }
                times_ids.push(ls_times_new);

            } //by month
            if (promotion.recurring == Recurring.YEAR) {
                times_ids.push(promotion.bundle_promotion_time_year_ids);
            } //bu year

            if (times_ids.length > 0 && times_ids[0].length > 0) {
                for (var i_pro = 0; i_pro < times_ids[0].length; i_pro++) {
                    times_promotion.push(self.pos.db.get_promotion_time_by_id(times_ids[0][i_pro]));
                }
            }

            var check_times = self.check_times_promotion(times_promotion, promotion);
            if (check_times == true || promotion.recurring == '') {
                msg_available[0] = true
            }
            if (msg_available[0] == false) {
                var msg_times = "Discount not available at the moment. Discount time: \n";
                for (var k = 0; k < times_promotion.length; k++) {
                    var from_hour = parseInt(times_promotion[k].start_hour * 100 / 100);
                    var from_minute = parseInt(((times_promotion[k].start_hour * 100) % 100) / 100 * 60);
                    var to_hour = parseInt(times_promotion[k].end_hour * 100 / 100);
                    var to_minute = parseInt(((times_promotion[k].end_hour * 100) % 100) / 100 * 60);
                    if (times_promotion[k].date) {
                        msg_times += times_promotion[k].date + '\t'
                    }
                    msg_times += from_hour + ':' + (from_minute > 0 ? from_minute : '00') + ' - ' + to_hour + ':' + (to_minute > 0 ? to_minute : '00') + '\n';
                }
                msg_available[1] = msg_times
            }
            return msg_available;
        },
        check_times_promotion: function (promotion_data, promotion) {
            var check = false;
            var date = new Date();
            var times = date.getHours() + (date.getMinutes() / 60);
            if (promotion_data.length <= 0) {
                return true;
            } else {
                for (var k = 0; k < promotion_data.length; k++) {
                    if (promotion_data[k].start_hour <= times && promotion_data[k].end_hour >= times) {
                        if (!promotion_data[k].date) {
                            check = true;
                            break;
                        } else {
                            var current_date = $.datepicker.formatDate(promotion.recurring == Recurring.YEAR && 'mm-dd' || 'yy-mm-dd', date);
                            // if (current_date == promotion_data[k].date) {
                            if (promotion_data[k].date.indexOf(current_date) != -1) {
                                check = true;
                                break;
                            }
                        }
                    }
                }
            }
            return check;
        },

        update_line_bill_promotion: function () {
            var self = this;
            var order = self.pos.get_order();
            var lines = order.get_orderlines();
            //Begin Vannh xu ly bill promotion
            var product_promotion = self.pos.db.get_product_by_id(self.pos.config.discount_product_id[0]);
            // Remove existing discounts
            var i = 0;
            var discount = 0;
            var bill_type = '';
            var bill_amount = 0;
            var min_bill_apply = 0;
            var bill_promotion_ids = [];
            var user_promotion = false;
            var voucher = [];
            while (i < lines.length) {
                if (lines[i].get_product() === product_promotion) {
                    bill_amount = lines[i].bill_amount;
                    bill_type = lines[i].bill_type;
                    min_bill_apply = lines[i].min_bill_apply;
                    bill_promotion_ids = lines[i].bill_promotion_ids;
                    user_promotion = lines[i].user_promotion;
                    voucher = lines[i].voucher;
                    order.remove_orderline(lines[i]);
                } else {
                    lines[i]['bill_promotion_ids'] = [];
                    i++;
                }
            }

            var total = order.br_get_total().toFixed(2);
            // Add discount
            if (total >= min_bill_apply) {
                if (bill_type == self.pos.DISCOUNT_PERCENT) {
                    discount = -bill_amount / 100.0 * total;
                }
                else if (bill_type == self.pos.DISCOUNT_AMOUNT) {
                    discount = -bill_amount;
                }

                if (discount < 0) {
                    if (self.pos.config.discount_product_id == false) {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        self.pos.gui.show_popup('error', {
                            'title': 'Discount',
                            'body': 'You do not config product for bill discount',
                        });
                    }
                    else {
                        order.add_product(product_promotion, {
                            price: discount,
                            bill_type: bill_type,
                            bill_amount: bill_amount,
                            min_bill_apply: min_bill_apply,
                            bill_promotion_ids: bill_promotion_ids,
                            promotion_id: bill_promotion_ids.length && bill_promotion_ids[0],
                            user_promotion: user_promotion,
                            product_master_id: product_promotion.id,
                            is_line_discount: true,
                            voucher: voucher
                        });
                        var lines_apply = order.get_orderlines();
                        var iindex = 0;
                        while (iindex < lines_apply.length) {
                            var line = lines_apply[iindex];
                            $.each(bill_promotion_ids, function(i, promo_id){
                                if(line['bill_promotion_ids'].indexOf(promo_id) === -1){
                                    line['bill_promotion_ids'].push(promo_id);
                                }
                            });

                            line['user_promotion'] = user_promotion;
                            iindex++;
                        }
                    }

                }
            }
        },

        exists_line_bill_promotion: function () {
            var self = this;
            var lines = self.pos.get_order().get_orderlines();
            var product = self.pos.db.get_product_by_id(self.pos.config.discount_product_id[0]);
            if (product == false) {
                return true;
            }
            var i = 0;
            while (i < lines.length) {
                if (lines[i].get_product() === product) {
                    return true;
                } else {
                    i++;
                }
            }
            return false;
        },
        create_line_bill_promotion: function (promotion, user_promotion, avaiable_quota, unlimited_quota) {
            var self = this;
            var order = self.pos.get_order();
            var lines = order.get_orderlines();
            var total = order.br_get_total().toFixed(2);
            var voucher_val = $('#div_voucher').val();

            if (promotion.user_quota_type == 'amount') {
                if (total > parseFloat(avaiable_quota) && parseFloat(avaiable_quota) > 0 && unlimited_quota == false) {
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    self.pos.gui.show_popup('error', {
                        title: _t('Invalid Discount'),
                        body: _t("Exceeded quota limit, discount is not applicable!"),
                    });
                    return false;
                }
            }

            var product = self.pos.db.get_product_by_id(self.pos.config.discount_product_id[0]);
            // Remove existing discounts
            var i = 0;
            while (i < lines.length) {
                if (lines[i].get_product() === product && promotion.is_hq_voucher == false) {
                    // order.remove_orderline(lines[i]);
                    // alert("Promotion is already applied");
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    self.pos.gui.show_popup('error', {
                        'title': 'Discount',
                        'body': "Discount is already applied"
                    });
                    return false;
                } else {
                    i++;
                }
            }
            var discount = 0;
            var bill_type = null;
            var bill_amount = 0;
            var min_bill_apply = promotion.minimum_spending;
            //CHeck apply with other promotion
            if (self.apply_with_other_promotion(promotion.is_apply) == true || promotion.is_hq_voucher == true) {
                // Add discount
                if (total >= min_bill_apply) {
                    if (promotion.discount_type == self.pos.DISCOUNT_PERCENT) {
                        discount = -promotion.discount_amount / 100.0 * total;
                        bill_type = self.pos.DISCOUNT_PERCENT;
                        bill_amount = promotion.discount_amount;
                    }
                    else if (promotion.discount_type == self.pos.DISCOUNT_AMOUNT) {
                        discount = -promotion.discount_amount;
                        bill_type = self.pos.DISCOUNT_AMOUNT;
                        bill_amount = promotion.discount_amount;
                    }

                    if (discount <= 0) {
                        var errors = order.check_error_status();
                        if (self.pos.config.discount_product_id == false) {
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            self.pos.gui.show_popup('error', {
                                'title': 'Discount',
                                'body': 'You did not config product for bill discount'
                            });
                            return false;
                        }
                        else if (errors) {
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            self.pos.gui.show_popup('error', {
                                'title': 'Warning',
                                'body': errors[0],
                            });
                            return false;
                        }
                        else {
                            if (!promotion.is_hq_voucher) {
                                order.add_product(product, {
                                    price: discount,
                                    bill_type: bill_type,
                                    bill_amount: bill_amount,
                                    min_bill_apply: min_bill_apply,
                                    bill_promotion_ids: [promotion.id],
                                    promotion_id: promotion.id,
                                    user_promotion: user_promotion,
                                    product_master_id: product.id,
                                    is_line_discount: true,
                                    voucher: [voucher_val]
                                });
                            } else {
                                order.set_discount_payment(voucher_val, {
                                    'journal_id': promotion.payment_method,
                                    'amount': -discount,
                                    'type': 'cash'
                                });
                            }
                            var lines_apply = order.get_orderlines();
                            var iindex = 0;
                            while (iindex < lines_apply.length) {
                                lines_apply[iindex]['bill_promotion_ids'].push(promotion.id);
                                lines_apply[iindex]['user_promotion'] = user_promotion;
                                iindex++;
                            }
                            if (promotion.is_non_sale_trans) {
                                if (promotion.user_quota_lines.length > 0) {
                                    var iindex = 0;
                                    while (iindex < self.pos.get_order().get_orderlines().length) {
                                        lines_apply[iindex].price = 0;
                                        lines_apply[iindex].price_unit = 0;
                                        lines_apply[iindex].price_flavor = 0;
                                        lines_apply[iindex].discount_amount = 0;
                                        lines_apply[iindex].non_sale = true;
                                        lines_apply[iindex].promotion_id = promotion.id;
                                        iindex += 1
                                    }
                                } else {
                                    self.pos.gui.show_popup('br-nonsale-validation-popup', {
                                        'title': _t('Validate Transaction'),
                                        'confirm': function () {
                                            var iindex = 0;
                                            while (iindex < self.pos.get_order().get_orderlines().length) {
                                                lines_apply[iindex].price = 0;
                                                lines_apply[iindex].price_unit = 0;
                                                lines_apply[iindex].price_flavor = 0;
                                                lines_apply[iindex].discount_amount = 0;
                                                lines_apply[iindex].non_sale = true;
                                                lines_apply[iindex].promotion_id = promotion.id;
                                                iindex += 1
                                            }
                                            self.pos.push_order(self.pos.get_order());
                                            self.pos.get_order().finalize();
                                            return true;
                                        }
                                    });
                                }

                                return true;
                            }
                            else if (promotion.is_hq_voucher == false) {
                                self.pos.gui.show_screen('payment');
                            }
                        }
                    }
                }
                else {
                    var msg = "";
                    if (promotion.discount_type == self.pos.DISCOUNT_PERCENT) {
                        msg = "Purchase at least " + min_bill_apply + " RM to get " + promotion.discount_amount.toFixed(2) + " % off";
                    }
                    if (promotion.discount_type == self.pos.DISCOUNT_AMOUNT) {
                        msg = "Purchase at least " + min_bill_apply + " RM to get " + promotion.discount_amount.toFixed(2) + " RM off";
                    }
                    // alert(msg);
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    self.pos.gui.show_popup('error', {
                        'title': 'Discount',
                        'body': msg
                    });
                    return false;
                }
            }
            else {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    'title': 'Discount',
                    'body': 'Cannot apply bill discount with another discount !',
                });
                return false;
            }

            return true;
        },

        apply_with_other_promotion: function (is_apply) {
            var self = this;
            if (is_apply == false) {
                if (self.pos.get_order().get_orderlines().filter(function (x) {
                        return x.product.id == self.pos.config.discount_promotion_bundle_id[0]
                    }).length > 0) {
                    return false;
                }
                else if (self.pos.get_order().get_orderlines().filter(function (x) {
                        return x.product.id == self.pos.config.discount_promotion_product_id[0]
                    }).length > 0) {
                    return false;
                }
                else {
                    return true;
                }

            }
            else {
                return true;
            }


        },


        // End Vannh bill promotion

        // TruongNN
        /** Get all promotions by product obj*/
        get_all_promotion_by_product: function (product) {
            //Ham loc promotion theo product or category of product
            var self = this;
            var product_id = product.id;
            var pos_category_id = product.pos_categ_id[0];
            var parent_pos_category_ids = [];
            parent_pos_category_ids.push(pos_category_id);
            var obj_pos_category = self.pos.db.get_category_by_id(pos_category_id);
            while (obj_pos_category && obj_pos_category.parent_id) {
                parent_pos_category_ids.push(obj_pos_category.parent_id[0]);
                obj_pos_category = self.pos.db.get_category_by_id(obj_pos_category.parent_id[0]);
            }

            var promotions = self.get_list_promotion(0);

            var arr_promotion = (promotions.length > 0) ? promotions : [];
            var match_promotions = []
            if (arr_promotion.length > 0) {
                for (var i = 0; i < arr_promotion.length; i++) {
                    if (arr_promotion[i].is_smart_detection == false) {
                        continue;
                    }
                    //bundle_promotion
                    if (arr_promotion[i].type_promotion === self.pos.PROMO_BUNDLE) {
                        var bundle_promotion_ids = arr_promotion[i].bundle_promotion_ids;
                        if (bundle_promotion_ids.length > 0) {
                            for (var j = 0; j < bundle_promotion_ids.length; j++) {
                                var promotion_bundle = self.pos.db.get_product_promotion_by_id(bundle_promotion_ids[j]);
                                if (promotion_bundle && !promotion_bundle.bundle_item && self.check_promo_products(promotion_bundle, parent_pos_category_ids, product_id)) {
                                    match_promotions.push(arr_promotion[i]);
                                    break;
                                }
                            }
                        }
                    }
                    //product_promotion
                    else if (arr_promotion[i].type_promotion === self.pos.PROMO_PRODUCT) {
                        var product_promotion_ids = arr_promotion[i].product_promotion_ids;
                        if (product_promotion_ids.length > 0) {
                            for (var j = 0; j < product_promotion_ids.length; j++) {
                                var promotion_product = self.pos.db.get_product_promotion_by_id(product_promotion_ids[j]);
                                if (promotion_product && self.check_promo_products(promotion_product, parent_pos_category_ids, product_id)) {
                                    match_promotions.push(arr_promotion[i]);
                                    break;
                                }
                            }
                        }
                    }
                }
            }

            return match_promotions;
        },

        check_promo_products: function (promotion_line, parent_pos_category_ids, product_id) {
            if ((promotion_line.product_id && promotion_line.product_id.indexOf(product_id) != -1)) {
                return true;
            } else {
                var found = false;
                for (var c in promotion_line.pos_category_id) {
                    if (parent_pos_category_ids.includes(promotion_line.pos_category_id[c])) {
                        found = true;
                        break;
                    }
                }
                return found
            }
        },

        /** Get all products by promotion obj return [[A], [B1, B2, B3],...]*/ // it would be nice if you explain what is A, B
        // Why put this function in helper
        get_all_products_by_promotion: function (promotion) {
            // Get all products related to promotion line and map them with that line
            var self = this;
            var lines = [];
            var promotion_line_ids = [];
            if (promotion.type_promotion === self.pos.PROMO_PRODUCT && promotion.product_promotion_ids.length > 0) {
                promotion_line_ids.push(promotion.product_promotion_ids);
            }
            else if (promotion.type_promotion === self.pos.PROMO_BUNDLE && promotion.bundle_promotion_ids.length > 0) {
                promotion_line_ids.push(promotion.bundle_promotion_ids);
            }
            var list = [];
            if (promotion_line_ids.length > 0) {
                list = self.pos.arr_promotion_product.filter(function (x) {
                    return promotion_line_ids[0].indexOf(x.id) != -1
                });
            }
            for (var ls = 0; ls < list.length; ls++) {
                if (list[ls].product_id.length > 0) {
                    var product_lines = [];
                    for (var k = 0; k < list[ls].product_id.length; k++) {
                        // list[ls].product_obj = this.pos.db.get_product_by_id(list[ls].product_id[k]);
                        // list[ls].used_time = 0;
                        // lines.push([list[ls]])
                        var product = this.pos.db.get_product_by_id(list[ls].product_id[k]);
                        // If product exist in pricelist and it's menu name
                        if(product.pricelist_item_ids.length && product.is_menu && this.pos.check_price_list(product.pricelist_item_ids)){
                            product_lines.push({
                                bundle_item: list[ls].bundle_item,
                                bundle_promotion_id: list[ls].bundle_promotion_id,
                                discount: list[ls].discount,
                                discount_amount: list[ls].discount_amount,
                                id: list[ls].id,
                                min_quantity: list[ls].min_quantity,
                                pos_category_id: list[ls].pos_category_id,
                                product_id: [product.id, product.display_name],
                                product_obj: product,
                                used_time: 0,
                                min_spending: list[ls].min_spending
                            });
                        }
                    }
                    lines.push(product_lines);
                }
                else if (list[ls].pos_category_id.length > 0) {
                    var arr_lines = [];
                    for (var k = 0; k < list[ls].pos_category_id.length; k++) {
                        var product_ids = this.pos.db.get_product_by_category(list[ls].pos_category_id[k]);
                        for (var i = 0; i < product_ids.length; i++) {
                            if(product_ids[i].pricelist_item_ids.length && product_ids[i].is_menu && this.pos.check_price_list(product_ids[i].pricelist_item_ids)) {
                                arr_lines.push({
                                    bundle_item: list[ls].bundle_item,
                                    bundle_promotion_id: list[ls].bundle_promotion_id,
                                    discount: list[ls].discount,
                                    discount_amount: list[ls].discount_amount,
                                    id: list[ls].id,
                                    min_quantity: list[ls].min_quantity,
                                    pos_category_id: [list[ls].pos_category_id[k]],
                                    product_id: [product_ids[i].id, product_ids[i].display_name],
                                    product_obj: product_ids[i],
                                    used_time: 0,
                                    min_spending: list[ls].min_spending
                                });
                            }
                        }
                    }
                    lines.push(arr_lines);
                }
            }
            return lines;
        },

        set_promotion_for_flavors: function (line_menuname, promotion_id, promotion_line) {
            var self = this;
            var flavors = self.get_flavor_by_menuname(line_menuname);
            for (var i = flavors.length - 1; i >= 0; i--) {
                flavors[i].promotion_id = promotion_id;
                flavors[i].product_promotion_id = promotion_line.id;
                flavors[i].is_bundle_item = promotion_line.bundle_item;
            }
        },

        promotion_lines_to_array_product_id: function (promotion_product_lines) {
            var res = [];
            for (var i = 0; i < promotion_product_lines.length; i++) {
                var a = promotion_product_lines[i];
                for (var j = 0; j < a.length; j++) {
                    var line = a[j];
                    res.push(line.product_id[0]);
                }
            }
            return res;
        },

        find_product_in_promotion: function (product_id, promotion_product_lines) {
            for (var i = 0; i < promotion_product_lines.length; i++) {
                for (var j = 0; j < promotion_product_lines[i].length; j++) {
                    var product_line = promotion_product_lines[i][j];
                    if (product_line.product_id && product_line.product_id[0] == product_id)
                        return product_line;
                }
            }
            return false;
        },

        get_promotion_line_by_id: function (id, promotion_product_lines) {
            for (var i = 0; i < promotion_product_lines.length; i++) {
                for (var j = 0; j < promotion_product_lines[i].length; j++) {
                    var product_line = promotion_product_lines[i][j];
                    if (product_line.id == id)
                        return product_line;
                }
            }
            return false;
        },

        set_promotion_for_orderlines: function (lines, promotion, promotion_product_lines) {
            var self = this;
            for (var i = lines.length - 1; i >= 0; i--) {
                if ((!lines[i].promotion_id || lines[i].promotion_id == promotion.id) && (lines[i].promotion_line_id && lines[i].promotion_line_id > 0)) {
                    var promotion_line = self.get_promotion_line_by_id(lines[i].promotion_line_id, promotion_product_lines);
                    if (promotion_line && promotion_line.bundle_promotion_id && promotion_line.bundle_promotion_id[0] == promotion.id) {
                        lines[i].promotion_id = promotion.id;
                        lines[i].is_bundle_item = promotion_line.bundle_item;
                        lines[i].product_promotion_id = lines[i].promotion_line_id;
                        self.set_promotion_for_flavors(lines[i], promotion.id, promotion_line);
                    }
                }
            }
        },
        // Why do we need this function, each menu already linked with its line
        get_flavor_by_menuname: function (line_menuname) {
            var self = this;
            var flavor = [];
            if (line_menuname.product.is_menu) {
                if (line_menuname.product.is_menu == true) {
                    var order = self.pos.get_order();
                    var lines = order.get_orderlines();
                    for (var i = 0; i < lines.length; i++) {
                        var line = lines[i];
                        if (line.parent_line) {
                            if (line.parent_line.id == line_menuname.id) {
                                flavor.push(line);
                            }
                        }
                    }
                }
            }
            return flavor;
        },

        validate_flavor: function () {
            var self = this;
            var order = self.pos.get_order();
            var lines = order.get_orderlines();
            for (var i = 0; i < lines.length; i++) {
                //not valid
                if (lines[i].product.is_menu) {
                    if (lines[i].product.is_menu == true && lines[i].error != false) {
                        return true;
                    }
                }
            }
            return false;
        },
    });
    return PromotionHelper;
});