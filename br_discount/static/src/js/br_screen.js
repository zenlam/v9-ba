odoo.define('br_discount.screen', function (require) {
    "use strict";

    var core = require('web.core');
    var _t = core._t;
    var gui = require('point_of_sale.gui');
    var Model = require('web.Model');
    var screens_req = require('point_of_sale.screens');
    var model_req = require('point_of_sale.models');
    var br_widgets = require('br_point_of_sale.widgets');
    var br_promotion = require('br_discount.br_promotion');
    var br_helper = require('br_discount.helper');
    var discount_widgets = require('br_discount.widgets'),
        VoucherWidget = discount_widgets.VoucherWidget;

    screens_req.ProductScreenWidget.include({
        start: function () {
            this._super();
            var self = this;
            this.helper = new br_helper({pos: self.pos});
            // TODO: all get_rate_outlet_user_quota should be placed in one function, no need to duplicate code
            this.$('.pay').click(function () {
                if (this.valid_order) {
                    var ls_promotion = self.helper.get_bill_promotion();
                    var selection_list = _.map(ls_promotion, function (ls_promotion) {
                        return {
                            label: ls_promotion.name,
                            item: ls_promotion,
                            image_url: window.location.origin + '/web/image?model=br.bundle.promotion&field=image_medium&id=' + ls_promotion.id,
                            instruction: ls_promotion.instruction,
                        };
                    });

                    var exits_line_bill = self.helper.exists_line_bill_promotion();
                    if (selection_list.length > 0 && (exits_line_bill == false)) {
                        self.gui.show_popup('selection_promotion', {
                            'title': _t('Do you want to apply this discount?'),
                            list: selection_list,
                            'confirm': function (obj_bill) {
                                // var is_apply_user = obj_bill.user_quota_type;
                                var ls_users = self.helper.get_users_for_promotion(obj_bill);
                                if (ls_users.length > 0) {
                                    var selection_list = _.map(ls_users, function (ls_user) {
                                        return {
                                            label: ls_user[1],
                                            value: ls_user[0]
                                        };
                                    });
                                    selection_list.sort(function (a, b) {
                                        var nameA = a.label.toLowerCase(),
                                            nameB = b.label.toLowerCase();
                                        // sort string ascending
                                        if (nameA < nameB)
                                            return -1;
                                        if (nameA > nameB)
                                            return 1;
                                        return 0
                                    });
                                    self.pos.gui.show_popup('br-login-user', {
                                        list: selection_list,
                                        need_confirm_product: !obj_bill.is_non_sale_trans || obj_bill.type_promotion != self.pos.PROMO_BILL,
                                        password: '',
                                        'confirm': function (user, pwd) {
                                            var promise = $.Deferred();
                                            var check_login = self.helper.check_login(user, pwd);
                                            check_login.then(function (uid) {
                                                var check_quota = self.helper.check_promotion_quota([false, uid, obj_bill.id]);
                                                check_quota.then(function (result) {
                                                    self.helper.create_line_bill_promotion(obj_bill, user, result[1], result[2]);
                                                    // self.gui.show_screen('payment');
                                                    promise.resolve();
                                                }, function (response, event) {
                                                    promise.reject();
                                                });
                                            }, function (resonse, event) {
                                                promise.reject();
                                            });
                                            return promise;
                                        }
                                    });
                                }

                                // Promotion normal --> check quota --> ok --> create a bill line

                                else {
                                    var check_quota = self.helper.check_promotion_quota([self.pos.config.outlet_id[0], false, obj_bill.id]);
                                    check_quota.then(function (result) {
                                        self.helper.create_line_bill_promotion(obj_bill, false, result[1], result[2]);
                                    });
                                }
                            },
                            'cancel': function (val) {
                                self.gui.show_screen('payment');
                            }
                        });

                    }
                    else {
                        //If there is no bill discount line then why need to check outlet quota for promotion ???
                        var obj_bill = self.pos.get_order().get_orderlines()[0].bill_promotion_ids;
                        var obj_promotion = self.pos.db.get_promotion_by_id(obj_bill);
                        var user_promotion = self.pos.get_order().get_orderlines()[0].user_promotion;
                        if (obj_bill.length > 0) {
                            var check_quota = self.helper.check_promotion_quota([self.pos.config.outlet_id[0], user_promotion, obj_bill[0]]);
                            check_quota.then(function (result) {
                                if (obj_promotion.user_quota_type == 'amount') {
                                    var total = self.pos.get_order().get_total_with_tax().toFixed(2);
                                    var available_quota = result[1];
                                    var is_unlimited_quota = result[2];
                                    if (total > parseFloat(available_quota) && parseFloat(available_quota) > 0 && is_unlimited_quota == false) {
                                        self.pos.get_order().remove_current_voucher_code();
                                        $('#div_voucher').val('');
                                        $('#div_voucher').attr('readonly', false);
                                        $('#div_voucher').css('background-color', '');
                                        self.pos.gui.show_popup('error', {
                                            title: _t('Invalid Discount'),
                                            body: _t("Exceeded quota limit, discount is not applicable!")
                                        });
                                        return;
                                    }
                                }
                                self.gui.show_screen('payment');
                            });
                        } else {
                            self.gui.show_screen('payment');
                        }
                    }
                }
            });

            this.item_list_widget = new br_widgets.BrItemMasterWidget(this, {});
            this.item_list_widget.replace(this.$('.product-list'));

            // Product mixin
            if (!this.item_mixin) {
                this.item_mixin = new br_widgets.ItemSelectMixin(this, {item_list_widget: this.item_list_widget});
            }
            this.voucher_widget = new VoucherWidget(this, {
                pos: this.pos,
            });
        }
    });

    screens_req.ProductCategoriesWidget.include({
        click_product_handler: function (product_node) {
            var self = this;
            this._super(product_node);
            var product_id = product_node.getAttribute('data-product-id');
            var product = self.pos.db.product_by_id[product_id];
            if (product) {
                //Begin Vannh xu ly bill promotion
                self.helper = new br_helper({pos: self.pos});
                self.helper.update_line_bill_promotion();
                //End Vannh xu ly bill promotion

                // //TruongNN
                //Get Promotion by product -> Smart detection
                var ls_promotion = self.helper.get_all_promotion_by_product(product);
                ls_promotion = jQuery.grep(ls_promotion, function (item, i) {
                    return (self.helper.check_time_bill_promotion(item)[0] == true)
                });
                if (ls_promotion.length > 0) {
                    var selection_list = _.map(ls_promotion, function (item) {
                        return {
                            label: item.name,
                            item: item,
                            image_url: window.location.origin + '/web/image?model=br.bundle.promotion&field=image_medium&id=' + item.id,
                            instruction: item.instruction,
                        };
                    });

                    self.gui.show_popup('selection_promotion', {
                        title: _t('Do you want to apply this discount?'),
                        list: selection_list,
                        confirm: function (promotion) {
                            //QuangNA: check is_non_sale
                            //TODO: move this check elsewhere for reuse
                            if (promotion.is_non_sale_trans == true) {
                                var line_menu = 0;
                                for (var k = 0; k < self.pos.get_order().get_orderlines().length; k++) {
                                    line_menu += self.pos.get_order().get_orderlines()[k].parent_line == undefined ? 1 : 0;
                                }
                                /*
                                 This promotion is prompted by smart detection when choose menu name
                                 therefore we must exclude that product from total number of menu names in shopping cart
                                 */
                                if (line_menu - 1 > 0) {
                                    self.pos.get_order().remove_current_voucher_code();
                                    $('#div_voucher').val('');
                                    $('#div_voucher').attr('readonly', false);
                                    $('#div_voucher').css('background-color', '');
                                    self.pos.gui.show_popup('error', {
                                        title: _t('Non sale discount'),
                                        body: _t('Empty shopping cart before use this discount!'),
                                    });
                                    return;
                                }
                            }

                            // Vannh STAFF user quota
                            var helper = new br_helper({pos: self.pos});
                            // var is_apply_user = promotion.user_quota_type;
                            var ls_users = helper.get_users_for_promotion(promotion);
                            if (ls_users.length > 0) {
                                var selection_list = _.map(ls_users, function (ls_user) {
                                    return {
                                        label: ls_user[1],
                                        value: ls_user[0]
                                    };
                                });
                                selection_list.sort(function (a, b) {
                                    return a.label > b.label;
                                });

                                self.pos.gui.show_popup('br-login-user', {
                                    list: selection_list,
                                    password: '',
                                    need_confirm_product: !promotion.is_non_sale_trans || promotion.type_promotion != self.pos.PROMO_BILL,
                                    'confirm': function (user, pass) {
                                        var promise = $.Deferred();
                                        var check_login = helper.check_login(user, pass);
                                        check_login.then(function (result) {
                                            var check_quota = helper.check_promotion_quota([false, result, promotion.id]);
                                            check_quota.then(function (result) {
                                                var order = self.pos.get_order();
                                                var lines = order.get_orderlines();
                                                for (var i = lines.length - 1; i >= 0; i--) {
                                                    if (lines[i].product.id == product_id) {
                                                        order.remove_orderline(lines[i]);
                                                        break;
                                                    }
                                                }
                                                self.PromotionButton = new br_promotion.PromotionButton(self, {pos: self.pos});
                                                self.PromotionButton.render_detail_promotion(promotion, user);
                                                promise.resolve();
                                            }, function (response, event) {
                                                promise.reject();
                                            });
                                        }, function (response, event) {
                                            promise.reject();
                                        });
                                        return promise;
                                    }
                                });
                            }

                            // Promotion normal --> check quota --> ok --> render promotion detail

                            else {
                                var order = self.pos.get_order();
                                var lines = order.get_orderlines();
                                for (var i = lines.length - 1; i >= 0; i--) {
                                    if (lines[i].product.id == product_id) {
                                        order.remove_orderline(lines[i]);
                                        break;
                                    }
                                }
                                this.PromotionButton = new br_promotion.PromotionButton(this, {pos: self.pos});
                                this.PromotionButton.render_detail_promotion(promotion, false);
                            }
                        }
                    });
                }
            }
        },
    });

    screens_req.PaymentScreenWidget.include({
        add_discount_payment: function () {
            // Add payment according to discount amount redeemed by Sales voucher
            var total_discount = 0;
            var order = this.pos.get_order();
            var total_order = order.get_total_with_tax();
            var payments = [];
            _.each(order.discount_payment, function (payment, voucher_code) {
                var unredeem_value = total_order < payment.amount && payment.type === 'cash' && total_order > 0 ? payment.amount - total_order : 0;
                var discount_paymentline = new model_req.Paymentline({}, {
                    order: order,
                    cashregister: order.get_cashregister_by_journal(payment.journal_id[0]),
                    pos: order.pos,
                    locked: true,
                    voucher_code: voucher_code,
                    unredeem_value: unredeem_value,
                });
                total_order -= payment.amount;
                discount_paymentline.set_amount(payment.amount, 0);
                payments.push(discount_paymentline);
                total_discount += payment.amount;
            });
            _.each(payments, function (pmt) {
                order.paymentlines.add(pmt);
            });
            return total_discount;
        },
        show: function () {
            this._super();
            this.show_discount_payment();
            this.render_paymentlines();
            this.order_changes();
        },
        show_discount_payment: function () {
            var order = this.pos.get_order();
            var total_w_tax = order.get_total_with_tax();
            if (total_w_tax != 0) {
                var discount_payment = this.add_discount_payment();
                if (discount_payment) {
                    if (discount_payment > total_w_tax) {
                        var tip_amount = discount_payment - total_w_tax;
                        order.set_tip(tip_amount);
                    }
                    if (this.pos.rounding_cashregister) {
                        var rounding_paymentline = order.add_rounding_payment(this.pos.rounding_cashregister);
                        rounding_paymentline.is_payment_rounding = true;
                    }
                    this.reset_input();
                    this.render_paymentlines();
                    this.order_changes();
                }
            }
        },
        remove_bill_discount: function () {
            var order = this.pos.get_order(),
                orderlines = order.get_orderlines();
            var bill_promotions = [];
            var product_promotion = this.pos.config.discount_product_id[0];
            for (var i in orderlines) {
                var line = orderlines[i];
                if (line.product.id == product_promotion) {
                    bill_promotions = bill_promotions.concat(line.bill_promotion_ids || []);
                    order.remove_orderline(line);
                }
            }
            var bill_promotions_set = bill_promotions.filter(function (item, pos) {
                return bill_promotions.indexOf(item) == pos;
            });
            var promo_index;
            $.each(bill_promotions_set, function (k, promo_id) {
                $.each(orderlines, function (z, line) {
                    if (line.bill_promotion_ids) {
                        promo_index = line.bill_promotion_ids.indexOf(promo_id);
                        while (promo_index !== -1) {
                            line.bill_promotion_ids.splice(promo_index, 1);
                            promo_index = line.bill_promotion_ids.indexOf(promo_id);
                        }
                    }
                });
            });
        },
        click_back: function () {
            this.remove_bill_discount();
            this._super();
            var order = this.pos.get_order();
            var total_orderline = order.get_orderlines().length;
            if (total_orderline == 0 && order.get_member_code()) {
                order.pos.gui.show_popup('confirm', {
                    'title': _t('Remove Member Code?'),
                    'body': _t('Shopping cart is empty! Do you want to remove the membership code from this order?'),
                    'confirm': function () {
                        order.remove_member();
                        order.pos.gui.current_screen.order_widget.renderElement();
                    }
                });
            }
        },
    })
});
