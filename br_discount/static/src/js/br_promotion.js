//Argggggg ..... KMN !!!
odoo.define('br_discount.br_promotion', function (require) {
    "use strict";
    var core = require('web.core');
    var QWeb = core.qweb;
    var _t = core._t;
    var gui = require('point_of_sale.gui');

    var screens = require('point_of_sale.screens');
    var br_helper = require('br_discount.helper');
    var Model = require('web.Model');


    var showEnum = {
        DISABLED: 1,
        ENABLED: 2
    };
    var DISCOUNT_TYPE = {
        BILL_DISCOUNT: 1,
        PRODUCT_DISCOUNT: 2,
        BUNDLE_DISCOUNT: 3
    };
    var PromotionButton = screens.ActionButtonWidget.extend({
        template: 'PromotionButton',
        init: function (parent, options) {
            var self = this;
            this._super(parent, options);
            this.click_product_promotion_handler = function (event) {
                self.click_product_promotion(this);
            };

            this.render_category_product_promotion_handler = function (event) {
                var promotion_id = this.getAttribute('data-promotion-id');
                var promotion = self.pos.db.promotion_items[promotion_id];
                var outlet_id = self.pos.config.outlet_id[0] > 0 ? self.pos.config.outlet_id[0] : 0;

                //Check non - sale require empty order
                if (promotion.is_non_sale_trans == true) {
                    //quangna check non sale
                    var line_menu = 0;
                    for (var k = 0; k < self.pos.get_order().get_orderlines().length; k++) {
                        line_menu += self.pos.get_order().get_orderlines()[k].parent_line == undefined ? 1 : 0;
                    }
                    if (line_menu > 0) {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        self.pos.gui.show_popup('error', {
                            title: _t('Non sale promotion'),
                            body: _t('Empty shopping cart before use this discount!'),
                        });
                        return;
                    }
                }

                // Promotion for Staff meal --> open popup to login

                var helper = new br_helper({pos: self.pos});
                var ls_users = helper.get_users_for_promotion(promotion);
                if (ls_users.length > 0) {
                    var selection_list = _.map(ls_users, function (ls_user) {
                        return {
                            label: ls_user[1],
                            value: ls_user[0]
                        };
                    });

                    selection_list.sort(function (a, b) {
                        var nameA = a.label.toLowerCase(), nameB = b.label.toLowerCase();
                        if (nameA < nameB) //sort string ascending
                            return -1;
                        if (nameA > nameB)
                            return 1;
                        return 0
                    });
                    self.pos.gui.show_popup('br-login-user', {
                        list: selection_list,
                        password: '',
                        need_confirm_product: !promotion.is_non_sale_trans || promotion.type_promotion != self.pos.PROMO_BILL,
                        'confirm': function (user, pass) {
                            var promise = $.Deferred();
                            var check_login = helper.check_login(user, pass);
                            check_login.then(function(result){
                                var check_quota = helper.check_promotion_quota([self.pos.config.outlet_id[0] > 0 ? self.pos.config.outlet_id[0] : 0, result, promotion.id]);
                                var onSuccess = function(response){
                                    self.render_detail_promotion(promotion, user);
                                    promise.resolve(response);
                                };
                                var onFail = function(response, event){
                                    promise.reject();
                                };
                                check_quota.then(onSuccess, onFail);
                            }, function(response, event){
                                promise.reject();
                            });
                            return promise;
                        }
                    });
                }

                // Promotion normal --> check quota --> ok --> create a promotion line

                else {
                    // If promotion isn't control by quota then render promotion detail immediately
                    if (promotion.user_quota_type == false && promotion.quota_type == false) {
                        self.render_detail_promotion(promotion, false);
                        return;
                    }
                    var check_quota = helper.check_promotion_quota([outlet_id, false, promotion.id]);
                    check_quota.then(function(result){
                       self.render_detail_promotion(promotion, false);
                    })
                }
            };
            this.click_button_apply_handler = function (event) {
                self.click_button_apply(this);
            };
            this.click_button_back_handler = function (event) {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.click_button_back(this);
            };
        },
        button_click: function () {
            this.render_category_promotion();
            this.pos.get_order().type_promotion = null;
        },
        render_category_promotion: function () {
            var self = this;
            var helper = new br_helper({pos: self.pos});

            var list_bill_promotion = helper.get_list_promotion(self.pos.PROMO_BILL);
            var list_product_promotion = helper.get_list_promotion(self.pos.PROMO_PRODUCT);
            var list_bundle_promotion = helper.get_list_promotion(self.pos.PROMO_BUNDLE);

            var layout_table = self.el.querySelector('.layout-table') ? self.el.querySelector('.layout-table') : $('.layout-table')[0];
            var layout_promotion = self.el.querySelector('.discount-promotion-screen') ? self.el.querySelector('.discount-promotion-screen') : $('.discount-promotion-screen')[0];
            //disabled widget product and categories
            self.show_element(layout_table, showEnum.DISABLED);

            //enabled widget promotion
            self.show_element(layout_promotion, showEnum.ENABLED);

            //Bill Promotion
            var bill_promotion = self.el.querySelector('.bill-promotion-content') ? self.el.querySelector('.bill-promotion-content') : $('.bill-promotion-content')[0];
            bill_promotion.innerHTML = '';
            if (bill_promotion.children.length == 0) {
                for (var i = 0; i < list_bill_promotion.length; i++) {
                    var promotion = this.render_promotion(list_bill_promotion[i]);
                    promotion.addEventListener('click', function (event) {
                        //TODO: refactor this function
                        var order = self.pos.get_order();
                        var lines = order.get_orderlines();
                        if (lines.length == 0) {
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            return self.pos.gui.show_popup('error', {
                                'title': 'Promotion Validation',
                                'body': 'Your shopping cart is empty'
                            });
                        }
                        //Begin Vannh Bill Promotion
                        var bill_id = parseInt(event.currentTarget.attributes[1].value);
                        self.helper = new br_helper({pos: self.pos});
                        var obj_bill = self.pos.db.get_promotion_by_id(bill_id);
                        var available_bill = self.helper.check_time_bill_promotion(obj_bill);
                        var is_apply_user = obj_bill.user_quota_type;
                        var ls_users = self.helper.get_users_for_promotion(obj_bill);
                        if (available_bill[0] == true) {
                            // Promotion for Staff meal --> open popup to login

                            if (ls_users.length > 0) {
                                var selection_list = _.map(ls_users, function (ls_user) {
                                    return {
                                        label: ls_user[1],
                                        value: ls_user[0]
                                    };
                                });
                                selection_list.sort(function (a, b) {
                                    var nameA = a.label.toLowerCase(), nameB = b.label.toLowerCase();
                                    if (nameA < nameB) //sort string ascending
                                        return -1;
                                    if (nameA > nameB)
                                        return 1;
                                    return 0;
                                });
                                self.pos.gui.show_popup('br-login-user', {
                                    list: selection_list,
                                    need_confirm_product: !obj_bill.is_non_sale_trans || obj_bill.type_promotion != self.pos.PROMO_BILL,
                                    password: '',
                                    'confirm': function (user, pass) {
                                        var done_checking = $.Deferred();
                                        var check_login = helper.check_login(user, pass);
                                        check_login.then(function(result){
                                            var check_quota = helper.check_promotion_quota([false, result, obj_bill.id]);
                                            var onSuccess = function(result){
                                                var avaiable_quota = result[1];
                                                var is_unlimited_quota = result[2];
                                                if (self.helper.create_line_bill_promotion(self.pos.db.get_promotion_by_id(bill_id), user, avaiable_quota, is_unlimited_quota) != false) {
                                                    done_checking.resolve();
                                                } else {
                                                    done_checking.reject();
                                                }
                                            };
                                            var onFail = function(response, event){
                                                done_checking.reject();
                                            };
                                            check_quota.then(onSuccess, onFail);
                                        },
                                        function(response, event){
                                            done_checking.reject();
                                        });
                                        return done_checking;
                                    }
                                });
                            }

                            // Promotion normal --> check quota --> ok --> create a bill line
                            else {
                                var check_quota = self.helper.check_promotion_quota([self.pos.config.outlet_id[0], false, obj_bill.id]);
                                check_quota.then(function(result){
                                    self.helper.create_line_bill_promotion(self.pos.db.get_promotion_by_id(bill_id), false, result[1], result[2]);
                                });
                            }
                        }
                        else {
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            self.pos.gui.show_popup('error', {
                                'title': 'Discount',
                                'body': available_bill[1],
                            });
                        }

                        //End Vannh Bill Promotion

                    });
                    bill_promotion.appendChild(promotion);
                }
            }

            //Product promotion
            var product_promotion = self.el.querySelector('.product-promotion-content') ? self.el.querySelector('.product-promotion-content') : $('.product-promotion-content')[0];
            product_promotion.innerHTML = '';
            if (product_promotion.children.length == 0) {
                for (var i = 0; i < list_product_promotion.length; i++) {
                    var promotion = this.render_promotion(list_product_promotion[i]);
                    promotion.addEventListener('click', this.render_category_product_promotion_handler);
                    product_promotion.appendChild(promotion);
                }
            }

            //Bundle promotion
            var bundle_promotion = self.el.querySelector('.bundle-promotion-content') ? self.el.querySelector('.bundle-promotion-content') : $('.bundle-promotion-content')[0];
            bundle_promotion.innerHTML = '';
            if (bundle_promotion.children.length == 0) {
                for (var i = 0; i < list_bundle_promotion.length; i++) {
                    var promotion = this.render_promotion(list_bundle_promotion[i]);
                    promotion.addEventListener('click', this.render_category_product_promotion_handler);
                    bundle_promotion.appendChild(promotion);
                }
            }

            $('.button.back.promotion').click(function () {
                if ($(this).hasClass('button back promotion')) {
                    if (layout_table.className.indexOf('oe_hidden') >= 0) {
                        /* Enabled widget product and categories */
                        self.show_element(layout_table, showEnum.ENABLED);
                        /* Disabled widget promotion */
                        self.show_element(layout_promotion, showEnum.DISABLED);
                        /* Trigger event*/
                        $('.pos-home').trigger('click');
                    }
                }
            });

        },
        render_promotion: function (promotion) {

            var image_url = this.get_promotion_image_url(promotion);
            var category_html = QWeb.render('CategoryPromotion', {
                widget: this,
                promotion: promotion,
                image_url: image_url
            });
            category_html = _.str.trim(category_html);
            var category_node = document.createElement('div');
            category_node.innerHTML = category_html;
            category_node = category_node.childNodes[0];

            //this.category_cache.cache_node(category.id, category_node);
            return category_node;


        },
        get_promotion_image_url: function (promotion) {
            //return window.location.origin + '/web/binary/image?model=br.bundle.promotion&field=image_medium&id=' + promotion.id;
            return window.location.origin + '/web/image?model=br.bundle.promotion&field=image&id=' + promotion.id;
        },
        check_promotion_over_promotion: function () {
            // Apply 2 promotions in same order is not allowed
            // except for promotion which can be applied with
            // another promotion
            // return: True - can't apply promotion, False - can apply promotion
            var self = this;
            var order = self.pos.get_order(),
                orderlines = order.orderlines;
            var bill_promotion_product = self.pos.config.discount_product_id[0];

            for (var i = 0; i < orderlines.length; i++) {
                var line = orderlines.models[i];
                //Check if bill promotion is applied
                if (line.product.id == bill_promotion_product) {
                    var can_apply_all = false;
                    for (var j in line.bill_promotion_ids) {
                        var promotion = self.pos.db.get_promotion_by_id(line.bill_promotion_ids[j]);
                        if (!promotion.is_hq_voucher) {
                            //If promotion can apply with other promotion then it's ok to use 2 promotions
                            return !promotion.is_apply;
                        }
                    }
                }
            }
            return false;
        },
        //TODO: REMOVE DUPLICATE CODE
        render_detail_promotion: function (promotion, user_promotion) {
            var self = this;
            var order = self.pos.get_order();
            var helper = new br_helper({pos: self.pos});
            document.getElementById("promotion_id").innerHTML = promotion.name;
            //check time ?
            var available = helper.check_time_bill_promotion(promotion);
            if (available[0] != true) {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    'title': 'Discount',
                    'body': available[1],
                });
                return;
            }
            if (self.check_promotion_over_promotion() && !promotion.is_apply) {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    'title': 'Discount',
                    'body': "Cannot apply bill discount with another discount !",
                });
                return;
            }
            //get lines by promotion
            var lines = helper.get_all_products_by_promotion(promotion); //self.pos.db.product_by_id;
            var list_container_wrap = self.el.querySelector('.categories') ? self.el.querySelector('.categories') : $('.categories')[0];
            var withpics = this.pos.config.iface_display_categ_images;
            //clear category-list
            var list_cates = $('.category-list');
            for (var p = 0; p <= list_cates.length - 1; p++) {
                var list_cate = list_cates[p];
                list_cate.remove();
            }

            if (list_container_wrap) {
                for (var i = 0; i < lines.length; i++) {
                    var promotion_products = lines[i];
                    //fill category-list
                    var list_container = document.createElement('div');
                    list_container.classList.add('category-list');

                    var title_limited = document.createElement('div');
                    title_limited.setAttribute("data-product-promotion-id", promotion_products[0] ? promotion_products[0].id : 0);
                    title_limited.setAttribute("data-promotion-user-id", user_promotion ? user_promotion : "");
                    title_limited.classList.add('promotion-title-row');
                    var tag_i = document.createElement('i');
                    tag_i.classList.add('fa');
                    tag_i.classList.add('fa-chevron-down');
                    var tag_span = document.createElement('span');
                    tag_span.classList.add('breadcrumb-button');
                    tag_span.appendChild(tag_i);
                    title_limited.appendChild(tag_span);
                    var title = document.createElement('span');
                    title_limited.appendChild(title);

                    if (promotion.type_promotion == self.pos.PROMO_PRODUCT) {
                        var discount = promotion_products[0] ? promotion_products[0].discount : 0;
                        var discount_amount = promotion_products[0] ? promotion_products[0].discount_amount : 0;
                        var min_quantity = promotion_products[0] ? promotion_products[0].min_quantity : 0;
                        if (discount > 0) {
                            title.innerHTML = "Required (Min Quantity " + min_quantity + ", discount " + discount + "%)";
                        } else if (discount_amount > 0) {
                            title.innerHTML = "Required (Min Quantity " + min_quantity + ", discount amount " + this.format_currency(discount_amount) + ")";
                        } else {
                            title.innerHTML = "Required (Min Quantity " + min_quantity + ")";
                        }
                    }
                    else {
                        var min_quantity = promotion_products[0] ? promotion_products[0].min_quantity : 0;
                        var min_spending = promotion_products[0] ? promotion_products[0].min_spending : 0;
                        var is_bundle_item = promotion_products[0] ? promotion_products[0].bundle_item : false;
                        var discount_amount = promotion_products[0] ? promotion_products[0].discount_amount : 0;
                        var discount = promotion_products[0] ? promotion_products[0].discount : 0;
                        if (!is_bundle_item) {
                            if (min_quantity) {
                                title.innerHTML = "Required (Min Quantity " + min_quantity + ')';
                            }
                            else {
                                title.innerHTML = "Required (Min Spending " + min_spending + ')';
                            }
                        }
                        else {
                            if (discount_amount) {
                                title.innerHTML = "Bundle Option (Quantity " + min_quantity + ", discount amount " + this.format_currency(discount_amount) + ")";
                            }
                            else {
                                title.innerHTML = "Bundle Option (Quantity " + min_quantity + ", discount " + discount + "%)";
                            }
                        }
                    }

                    list_container.classList.add('quantity-list');
                    list_container.appendChild(title_limited);

                    for (var m = 0; m < promotion_products.length; m++) {
                        var product_promotion = promotion_products[m];
                        var product = product_promotion.product_obj;
                        if (product) {
                            var product_node = self.render_product(product);
                            product_node.addEventListener('click', this.click_product_promotion_handler);
                            list_container.appendChild(product_node);
                        }
                    }
                    list_container_wrap.insertBefore(list_container, list_container_wrap.children[list_container_wrap.childElementCount - 1]);
                }

                var btns = [
                    self.el.querySelector('.breadcrumb-button-apply') ? self.el.querySelector('.breadcrumb-button-apply') : $('.breadcrumb-button-apply')[0],
                    self.el.querySelector('.breadcrumb-button-back') ? self.el.querySelector('.breadcrumb-button-back') : $('.breadcrumb-button-back')[0]
                ];
                for (i = 0; i < btns.length; i++) {
                    btns[i].setAttribute("data-promotion-id", promotion.id);
                    btns[i].setAttribute("data-promotion-user-id", user_promotion ? user_promotion : "");
                }
            }

            var layout_promotion = self.el.querySelector('.discount-promotion-screen') ? self.el.querySelector('.discount-promotion-screen') : $('.discount-promotion-screen')[0];
            //disabled layout promotion
            self.show_element(layout_promotion, showEnum.DISABLED);

            var layout_table = self.el.querySelector('.layout-table') ? self.el.querySelector('.layout-table') : $('.layout-table')[0];
            self.show_element(layout_table, showEnum.ENABLED);
            self.show_button_apply_back(showEnum.ENABLED);

            //Prevent duplicate event listeners on same element
            $('.breadcrumb-button-apply').replaceWith($('.breadcrumb-button-apply').clone());
            $('.breadcrumb-button-back').replaceWith($('.breadcrumb-button-back').clone());

            var breadcrumb_button_apply = self.el.querySelector('.breadcrumb-button-apply') ? self.el.querySelector('.breadcrumb-button-apply') : $('.breadcrumb-button-apply')[0];
            var breadcrumb_button_back = self.el.querySelector('.breadcrumb-button-back') ? self.el.querySelector('.breadcrumb-button-back') : $('.breadcrumb-button-back')[0];
            if (breadcrumb_button_apply && breadcrumb_button_back) {
                breadcrumb_button_apply.addEventListener('click', this.click_button_apply_handler);
                breadcrumb_button_back.addEventListener('click', this.click_button_back_handler);
            }

            $('.promotion-title-row').click(function () {

                if ($(this).find("i").hasClass('fa-chevron-down')) {
                    $(this).find("i").addClass('fa-chevron-up');
                    $(this).find("i").removeClass('fa-chevron-down');
                    $(this).parent().children(".product").hide(600);
                }
                else {
                    $(this).find("i").addClass('fa-chevron-down');
                    $(this).find("i").removeClass('fa-chevron-up');
                    $(this).parent().children(".product").show(600);
                }
            });
        },
        render_product_promotion: function (products) {
            var self = this;
            var list_container_wrap = self.el.querySelector('.categories') ? self.el.querySelector('.categories') : $('.categories')[1];
            var withpics = this.pos.config.iface_display_categ_images;
            //clear category-list
            var list_cates = self.el.querySelectorAll('.category-list');
            for (var p = list_cates.length - 1; p >= 0; p--) {
                var list_cate = list_cates[p];
                list_cate.remove();
            }

            if (list_container_wrap) {
                //fill product
                var product_list = jQuery.grep(products, function (a) {
                    return a.is_menu == true;
                });

                for (var k = 0; k < product_list.length; k++) {
                    var list_container = document.createElement('div');
                    list_container.classList.add('category-list');
                    var product_node = self.render_product(product_list[k]);
                    product_node.addEventListener('click', this.switch_category_handler);
                    list_container.appendChild(product_node);
                    list_container_wrap.insertBefore(list_container, list_container_wrap.children[list_container_wrap.childElementCount]);
                }
            }
        },
        render_product: function (product) {
            var image_url = this.get_product_image_url(product);
            var product_html = QWeb.render('ProductPromotion', {
                widget: this,
                product: product,
                image_url: this.get_product_image_url(product),
            });
            var product_node = document.createElement('div');
            product_node.innerHTML = product_html;
            product_node = product_node.childNodes[1];
            //this.product_cache.cache_node(product.id, product_node);
            return product_node;
        },
        get_product_image_url: function (product) {
            return window.location.origin + '/web/binary/image?model=product.product&field=image_medium&id=' + product.id;
        },
        click_product_promotion: function (product_node) {
            var self = this;
            if (product_node.getAttribute('data-product-id')) {
                var product_id = product_node.getAttribute('data-product-id');
                var product = self.pos.db.product_by_id[product_id];
                if (product) {
                    //Truongnn add promotion-line-id
                    var promotion_line_id = product_node.parentNode.firstChild.getAttribute('data-product-promotion-id');
                    if (promotion_line_id !== undefined)
                        self.pos.get_order().add_product(product,
                            {promotion_line_id: parseInt(promotion_line_id)}
                        );
                    else
                        self.pos.get_order().add_product(product);
                    //FIXME: Should create this.helper elsewhere to avoid create new instance every times
                    //Begin Vannh xu ly bill promotion
                    self.helper = new br_helper({pos: self.pos});
                    self.helper.update_line_bill_promotion();
                    //End Vannh xu ly bill promotion
                }
            }
        },
        show_element: function (layout_element, flag) {
            if (flag == showEnum.DISABLED) {
                // layout_element.className = layout_element.className.concat(' oe_hidden');
                layout_element.classList.add("oe_hidden");
            }
            if (flag == showEnum.ENABLED) {
                // layout_element.className = layout_element.className.replace('oe_hidden','');
                layout_element.classList.remove("oe_hidden");
            }
        },
        show_button_apply_back: function (flag) {
            var self = this;
            var breadcrumb_button_apply_back = self.el.querySelector('.breadcrumb-button-apply-back') ? self.el.querySelector('.breadcrumb-button-apply-back') : $('.breadcrumb-button-apply-back')[0];
            if (breadcrumb_button_apply_back) {
                var rightpane_header = self.el.querySelector('.rightpane-header') ? self.el.querySelector('.rightpane-header') : $('.rightpane-header')[0];
                if (flag == showEnum.ENABLED) {
                    //disabled rightpane-header;
                    //self.show_element(rightpane_header, showEnum.DISABLED);
                    self.show_element(breadcrumb_button_apply_back, flag);
                }
                if (flag == showEnum.DISABLED) {
                    //self.show_element(breadcrumb_button_apply_back, flag);
                    self.show_element(rightpane_header, showEnum.ENABLED);
                }
            }
        },
        show_home_page: function () {
            var self = this;
            var breadcrumb_button_apply_back = self.el.querySelector('.breadcrumb-button-apply-back') ? self.el.querySelector('.breadcrumb-button-apply-back') : $('.breadcrumb-button-apply-back')[0];
            self.show_element(breadcrumb_button_apply_back, showEnum.DISABLED);
            var rightpane_header = self.el.querySelector('.rightpane-header') ? self.el.querySelector('.rightpane-header') : $('.rightpane-header')[0];
            self.show_element(rightpane_header, showEnum.ENABLED);
            $('.pos-home').trigger('click');
        },
        check_promotion_popup: function (title, body) {
            this.pos.gui.show_popup('error',
                {
                    title: _t(title),
                    body: _t(body),
                });
        },
        check_promotion_product_qty: function (promotion) {
            // This check if for bundle promotion only
            var self = this;
            var promo = promotion; // now we can access promotion from deeper scope
            // return new Model('br.bundle.promotion').call('get_promotion_line', [promotion.id])
            //     .then(function (result) {
            var result = {};
            for (var k in promotion.promotion_lines) {
                var l = promotion.promotion_lines[k];
                result[l.id] = {'min_quantity': l.min_quantity}
            }
            var flag = true;
            if (result) {
                var order_line = self.pos.get_order().get_orderlines();
                var isNoneSale = promotion['is_none_sale_trans'];
                // prepare promotion line, count quantity per each promotion line
                var merge_line = {};
                for (var i = 0; i < order_line.length; i++) {
                    var line = order_line[i];
                    var promotion_line_id = line.promotion_line_id;
                    if (promotion_line_id) {
                        if (!(promotion_line_id in merge_line)) {
                            merge_line[promotion_line_id] = 0;
                        }
                        merge_line[promotion_line_id] += line.quantity;
                    }
                }
                // check quantity
                $.each(merge_line, function (index, value) {
                    if (index in result
                        && !isNoneSale
                        && value % result[index]['min_quantity'] > 0
                        && promo.type_promotion != DISCOUNT_TYPE.PRODUCT_DISCOUNT
                    ) {
                        self.check_promotion_popup(
                            "Invalid Discount",
                            "Select enough products to apply this discount!");
                        flag = false;
                        return false;
                    }
                    if (index in result
                        && isNoneSale
                        && value > result[index]['min_quantity']
                    ) {
                        self.check_promotion_popup(
                            "Invalid Discount",
                            "Select enough products to apply this discount!");
                        flag = false;
                        return false;
                    }
                });
            }
            return flag

        },
        apply_promotion: function (promotion, is_voucher, available_quota, is_unlimited_quota, user_promotion) {
            var self = this;
            if (promotion.type_promotion == self.pos.PROMO_PRODUCT) {
                if (!self.pos.config.discount_promotion_product_id) {
                    self.pos.gui.show_popup('error', {
                        title: _t('Unconfigured Discount'),
                        body: _t('Product Discount is not configured for this POS!'),
                    });
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    return;
                }
                self.apply_product_promotion(promotion, is_voucher, available_quota, is_unlimited_quota, user_promotion);
            }
            else if (promotion.type_promotion == self.pos.PROMO_BUNDLE) {
                if (!self.pos.config.discount_promotion_bundle_id) {
                    self.pos.gui.show_popup('error', {
                        title: _t('Unconfigured Discount'),
                        body: _t('Bundle Discount is not configured for this POS!'),
                    });
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                }
                else {
                    var check = self.check_promotion_product_qty(promotion);
                    if (check == true) {
                        self.apply_bundle_promotion(promotion, is_voucher, available_quota, is_unlimited_quota, user_promotion);
                    }
                }
            }
            //Begin Vannh xu ly bill promotion
            self.helper = new br_helper({pos: self.pos});
            self.helper.update_line_bill_promotion();
            //End Vannh xu ly bill promotion
        },
        click_button_apply: function (element) {
            var self = this;
            if (element.getAttribute('data-promotion-id')) {
                var promotion_id = element.getAttribute('data-promotion-id');
                var promotion = self.pos.db.promotion_items[promotion_id];
                var user_promotion = false;
                if (element.getAttribute('data-promotion-user-id')) {
                    user_promotion = element.getAttribute('data-promotion-user-id');
                }
                var is_voucher = false;
                if (!promotion) {
                    //di theo huong voucher
                    promotion = self.pos.db.get_voucher_by_id(promotion_id);
                    is_voucher = true;
                }
                if (!promotion) {
                    return;
                }
                var outlet_id = self.pos.config.outlet_id[0] > 0 ? self.pos.config.outlet_id[0] : 0;
                //check available oulet or user quota ?
                if (promotion.quota_type || promotion.user_quota_type) {
                    var helper = new br_helper({pos: self.pos});
                    var check_quota = helper.check_promotion_quota([outlet_id, user_promotion, promotion.id]);
                    check_quota.then(function(result){
                        self.apply_promotion(promotion, is_voucher, result[1], result[2], user_promotion);
                    });
                } else {
                    self.apply_promotion(promotion, is_voucher, 0, true, user_promotion);
                }
            }
        },
        click_button_back: function (element) {
            var self = this;
            $('#div_voucher').attr('readonly', false);
            $('#div_voucher').css('background-color', '');
            self.render_category_promotion();
        },

        /* remove line discount for this promotion if it existed */
        remove_discount_line_by_promotion: function (promotion) {
            var self = this;
            try {
                // Exception appears when promotion product is not configured ?
                var order = self.pos.get_order();
                var lines = order.get_orderlines();
                var product_discount;
                if (promotion.type_promotion === self.pos.PROMO_BILL)
                    product_discount = self.pos.db.get_product_by_id(self.pos.config.discount_product_id[0]);
                else if (promotion.type_promotion === self.pos.PROMO_PRODUCT)
                    product_discount = self.pos.db.get_product_by_id(self.pos.config.discount_promotion_product_id[0]);
                else if (promotion.type_promotion === self.pos.PROMO_BUNDLE)
                    product_discount = self.pos.db.get_product_by_id(self.pos.config.discount_promotion_bundle_id[0]);

                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].product.id === product_discount.id && lines[i].promotion_id == promotion.id) {
                        order.remove_orderline_when_click_apply(lines[i]);
                    }
                }
            } catch (e) {
                // FIXME: This message isn't clear and may be wrong in some cases
                self.pos.gui.show_popup('error', {
                    title: _t('Unconfigured Discount'),
                    body: _t('Bundle Discount is not configured for this POS!'),
                });
            }
        },
        count_required_products: function (promotion_product_lines) {
            var req = 0;
            for (var i = 0; i < promotion_product_lines.length; i++) {
                if (promotion_product_lines[i][0] && !promotion_product_lines[i][0].bundle_item)
                    req += 1;
            }
            return req;
        },
        check_condition_promotion: function (orderlines, promotion, promotion_product_lines) {
            var self = this;
            var promotion_lines = self.pos.db.product_promotion;
            //Truongnn: sp nam trong chuong trinh km va là menu_name, Group lại để tính tỷ lệ
            var lines = {};
            var sum_price = 0;

            //Group orderlines with same promotion line.
            for (var i = 0; i < orderlines.length; i++) {
                var promotion_line = promotion_lines[[orderlines[i].promotion_line_id]];
                if (promotion_line) {
                    var promotion_id = promotion_line.bundle_promotion_id[0];
                } else {
                    promotion_id = undefined;
                }
                if (promotion.id == promotion_id && orderlines[i].parent_line == undefined) {
                    // if (!promotion.is_voucher || (promotion.is_voucher && !orderlines[i].voucher)){
                    sum_price += orderlines[i].quantity * orderlines[i].price;
                    if (lines[orderlines[i].promotion_line_id] == undefined) {
                        lines[orderlines[i].promotion_line_id] = {
                            quantity: orderlines[i].quantity,
                            price: orderlines[i].price,
                            rate: 0,
                            rate_bundle: 0
                        };
                    }
                    else {
                        lines[orderlines[i].promotion_line_id] = {
                            quantity: orderlines[i].quantity + lines[orderlines[i].promotion_line_id].quantity,
                            price: orderlines[i].price + lines[orderlines[i].promotion_line_id].price,
                            rate: 0,
                            rate_bundle: 0
                        };
                    }
                    // }
                    // if(promotion.is_voucher && orderlines[i].voucher){
                    //     promo_used_voucher += 1
                    // }
                }
            }

            //Calculate rate
            var rate = false;
            var count = 0;

            var rate_bundle = false;
            var count_bundle = 0;

            for (var promo_line_id in lines) {
                var l = lines[promo_line_id];
                //where is the comment ? what's happening here ?
                for (i = 0; i < promotion_product_lines.length; i++) {
                    var promotion_product_line = promotion_product_lines[i];
                    var min_spending = promotion_product_line[0] ? promotion_product_line[0].min_spending : 0;
                    var min_qty = promotion_product_line[0] ? promotion_product_line[0].min_quantity : 0;
                    if (promo_line_id == promotion_product_line[0].id) {
                        if (!promotion_product_line[0].bundle_item) {
                            count += 1;
                            if (min_spending > 0) {
                                l.rate = l.price / min_spending;
                            }
                            else if (min_qty > 0) {
                                l.rate = l.quantity / min_qty;
                            }

                            rate = Math.floor(rate != false ? Math.min(rate, l.rate) : l.rate);
                            if (rate < 1) {
                                return [rate, sum_price];
                            }
                        }
                        else {
                            count_bundle += 1;
                            if (min_spending > 0) {
                                l.rate_bundle = l.price / min_spending;
                            }
                            else if (min_qty > 0) {
                                l.rate_bundle = l.quantity / min_qty;
                            }

                            rate_bundle = Math.floor(rate_bundle != false ? Math.min(rate_bundle, l.rate_bundle) : l.rate_bundle);
                            if (rate_bundle < 1) {
                                return [rate_bundle, sum_price];
                            }
                        }
                    }
                }

            }

            //Kiem tra danh sach san pham phai lua chon
            var required_products = 0;
            var required_products_bundle = 0;
            for (i = 0; i < promotion_product_lines.length; i++) {
                if (promotion_product_lines[i][0] && !promotion_product_lines[i][0].bundle_item)
                    required_products += 1;
                if (promotion_product_lines[i][0] && promotion_product_lines[i][0].bundle_item)
                    required_products_bundle += 1;
            }
            if (count < required_products || (count_bundle < required_products_bundle) || (rate_bundle < rate || rate_bundle == false)) {
                rate = -1;
                return [rate, sum_price];
            }
            return [rate, sum_price];
        },
        get_times_product_in_store: function (product_id) {
            var self = this;
            var order = self.pos.get_order();
            var orderlines = order.get_orderlines();
            var times = 0;
            for (var i = 0; i < orderlines.length; i++) {
                if (orderlines[i].product.id == product_id)
                    times++;
            }
            return times;
        },
        distribute_price: function (line, orderlines, amount) {
            //TODO: Refactor this function
            var self = this;
            var errors = self.pos.get_order().check_error_status();
            if (errors) {
                var error = errors.join('\n');
                self.pos.gui.show_popup('error', {
                    'title': 'Discount',
                    'body': error,
                });
                return false;
            }
            // Why need to search through all orderlines just to get line's flavours
            // we already have items property right ??
            for (var i = 0; i < orderlines.length; i++) {
                if (amount > 0 && orderlines[i].parent_line === line && line.price > 0) {
                    orderlines[i].discount_amount = (amount / line.price) * (orderlines[i].price_flavor * orderlines[i].quantity * orderlines[i].bom_quantity);
                }
            }
            return true;
        },

        get_bundle_discount_amount: function (rate) {
            // Get discount amount for each parent orderline that bounded to promotion
            var self = this;
            var orderlines = this.pos.get_order().get_orderlines();
            var promotion_lines = self.pos.db.product_promotion;
            var promotion_line_values = {};
            var parent_orderlines = orderlines.filter(function (l) {
                //Get total amount per promotion line
                var check = l.parent_line == undefined;
                if (check) {
                    if (l.promotion_line_id in promotion_line_values) {
                        promotion_line_values[l.promotion_line_id] += l.price;
                    } else {
                        promotion_line_values[l.promotion_line_id] = l.price;
                    }
                }
                return check;
            });
            var res = {};
            for (var i = 0; i < parent_orderlines.length; i++) {
                var line = parent_orderlines[i];
                var promotion_line = promotion_lines[[line.promotion_line_id]];
                if (promotion_line) {
                    res[line.id] = {amount: 0, percentage: 0};
                    if (promotion_line.discount_amount > 0) {
                        //If total value is greater than discount amount, distribute amount to each line by its % on total
                        var total = promotion_line_values[line.promotion_line_id] / rate;
                        if (total > promotion_line.discount_amount) {
                            res[line.id].amount = line.price * promotion_line.discount_amount / total;
                        } else {
                            res[line.id].amount = line.price;
                        }
                    }
                    else if (promotion_line.discount) {
                        res[line.id].percentage = promotion_line.discount;
                    }
                }
            }
            return res
        },

        get_discount_bundle_promotion: function (line, promotion, promotion_product_lines, rate) {
            var self = this;
            var discount = {amount: 0, percentage: 0};
            var promotion_lines = self.pos.db.product_promotion;
            var promotion_line = promotion_lines[[line.promotion_line_id]];
            if (promotion_line) {
                var promotion_id = promotion_line.bundle_promotion_id[0];
            } else {
                promotion_id = undefined;
            }
            if (promotion_id == promotion.id && line.parent_line == undefined) {
                var orderlines = this.pos.get_order().get_orderlines();
                var promoline_orderlines = orderlines.filter(function (x) {
                    return x.promotion_line_id == promotion_line.id
                });
                if (promotion_line.discount_amount > 0) {
                    var total_lines_price = 0;
                    for (var i = 0; i < promoline_orderlines.length; i++) {
                        var l = promoline_orderlines[i];
                        total_lines_price += l.price;
                        l.visisted = true;
                    }
                    discount.amount = Math.min(total_lines_price, promotion_line.discount_amount * rate)
                } else if (promotion_line.discount) {
                    discount.percentage = promotion_line.discount;
                }
            }
            return discount;
        },
        apply_bundle_promotion: function (promotion, is_voucher, available_quota, is_unlimited_quota, user_promotion) {
            var self = this;
            var order = self.pos.get_order();
            var orderlines = order.get_orderlines();
            var helper = new br_helper({pos: self.pos});
            var voucher_val = $('#div_voucher').val();
            //Lay Promotion Lines
            var promotion_product_lines = helper.get_all_products_by_promotion(promotion);
            if (promotion_product_lines.length <= 0) {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    title: _t('Invalid Discount'),
                    body: _t("There is no promotion line in this discount!"),
                });
                return;
            }

            //Lay discount Product in pos config
            var discount_line = self.pos.db.get_product_by_id(self.pos.config.discount_promotion_bundle_id[0]);
            if (discount_line == undefined) {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    title: _t('Invalid Discount Configuration'),
                    body: _t("Product Discount is not configured for this POS!")
                });
                return;
            }


            //Tinh toan ty le de xac dinh gia trị khuyen mai
            var ls_check_result = self.check_condition_promotion(orderlines, promotion, promotion_product_lines);
            var rate = ls_check_result[0];
            var sum_price = ls_check_result[1];
            // Xu ly truong hop type quota la Amount
            if (promotion.user_quota_type == 'amount') {
                if (sum_price > parseFloat(available_quota) && parseFloat(available_quota) > 0 && is_unlimited_quota == false) {
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
            else {
                if (rate > available_quota && is_unlimited_quota == false) {
                    // rate = available_quota;
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    self.pos.gui.show_popup('error', {
                        title: _t('Invalid Discount'),
                        body: _t("Exceeded quota limit, discount is not applicable!"),
                    });
                    return;
                }
            }

            if (rate < 1) {
                self.pos.gui.show_popup('error', {
                    title: _t('Invalid Discount'),
                    body: _t("Select enough products to apply this discount!"),
                });
                //re-set product_promotion_id order lines store
                for (var index = 0; index < orderlines.length; index++) {
                    orderlines[index].product_promotion_id = false;
                    orderlines[index].user_promotion = false;
                }
                return;
            }

            // user chỉ được dùng promotion 1 lần đúng với qty điền trong cột min qty
            if ((rate > 1) && (promotion.is_non_sale_trans == true || promotion.is_voucher == true)) {
                var rate_per_voucher = rate;
                if (promotion.is_voucher) {
                    var vouchers = order.use_voucher;
                    //Redundant empty element is counted in place of new voucher
                    rate_per_voucher = rate / vouchers.length;
                }
                if (rate_per_voucher > 1) {
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                    self.pos.gui.show_popup('error', {
                        title: _t('Invalid Discount'),
                        body: _t("Allow use promotion 1 time!")
                    });
                    //re-set product_promotion_id order lines store
                    for (var index = 0; index < orderlines.length; index++) {
                        orderlines[index].product_promotion_id = false;
                        orderlines[index].user_promotion = false;
                    }
                    return;
                }
            }
            //Remove discount line existed in store to re-process
            self.remove_discount_line_by_promotion(promotion);

            //Dua tren rate de remove promotion_id o orderline ko dc tinh promotion
            self.remove_promotion_for_lines_byrate(orderlines, promotion, promotion_product_lines, rate);

            //So sanh sp o gio hang va promotion de tinh discount
            var discount = {amount: 0, percentage: 0};
            var promotion_lines = self.pos.db.product_promotion;

            var line_discounts = self.get_bundle_discount_amount(rate);
            //Truongnn: sp nam trong chuong trinh km va là menu_name, Group lại để tính tỷ lệ
            for (var i = 0; i < orderlines.length; i++) {
                var promotion_line = promotion_lines[[orderlines[i].promotion_line_id]];
                if (promotion_line) {
                    var promotion_id = promotion_line.bundle_promotion_id[0];
                } else {
                    promotion_id = undefined;
                }
                if (promotion.id == promotion_id) {
                    orderlines[i].rate_promotion = rate;
                    orderlines[i].user_promotion = user_promotion;
                    if (!orderlines[i].voucher) {
                        orderlines[i].set_voucher(voucher_val);
                    }
                    _.each(orderlines[i].items, function (item) {
                        item.rate_promotion = rate;
                        item.user_promotion = user_promotion;
                    })
                }
                if (promotion.id == promotion_id && !orderlines[i].is_flavour_item) {
                    //Discount processing
                    // var d = self.get_discount_bundle_promotion(orderlines[i], promotion, promotion_product_lines, rate);
                    var d = line_discounts[orderlines[i].id];
                    var discount_amount = 0;
                    if (d.amount > 0) {
                        orderlines[i].discount_amount = d.amount;
                        discount_amount += d.amount;
                    }
                    else if (d.percentage > 0) {
                        orderlines[i].discount_amount = orderlines[i].price * (d.percentage / 100);
                        discount_amount = orderlines[i].discount_amount;
                    }

                    //Thuc hien phan bo discount cho tung Flavors
                    if (discount_amount > 0) {
                        var distribute = self.distribute_price(orderlines[i], orderlines, discount_amount);
                        if (distribute == false) {
                            return;
                        }
                        discount.amount += discount_amount
                    }
                }
            }

            //Add line discount for this promotion
            if (discount.amount > 0) {
                discount_line.purchase_ok = false;
                order.add_product(discount_line, {
                    quantity: 1,
                    price: -discount.amount,
                    promotion_id: promotion.id,
                    rate_promotion: rate,
                    product_master_id: discount_line.id,
                    voucher: [voucher_val]
                });
            }
            self.show_home_page();
            //Quangna: truong hop neu dung voucher
            if (is_voucher == true) {
                if (voucher_val.length > 0) {
                    //refactor this
                    order.use_voucher.push(voucher_val);
                    order.set_voucher(order.use_voucher);
                }
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
            }

            //Nhan dien cac order lines nhan promotion nay
            helper.set_promotion_for_orderlines(orderlines, promotion, promotion_product_lines);

            //NON SALE
            if (promotion.is_non_sale_trans == true) {
                var lines_apply = order.get_orderlines();
                var lines = lines_apply.filter(function (x) {
                    return x.is_flavour_item == false && x.price > 0;
                });
                var selection_list = _.map(lines, function (line) {
                    return {
                        label: line.product.display_name + '/' + line.quantity,
                        item: line
                    };
                });

                // self.pos.gui.show_popup('br-nonsale-popup', {
                //     'title': _t('Product used/Quantity: '),
                //     list: selection_list,
                //     'confirm': function (val_note) {
                var iindex = 0;
                while (iindex < self.pos.get_order().get_orderlines().length) {
                    lines_apply[iindex].price = 0;
                    lines_apply[iindex].price_unit = 0;
                    lines_apply[iindex].price_flavor = 0;
                    lines_apply[iindex].discount_amount = 0;
                    lines_apply[iindex].non_sale = true;
                    lines_apply[iindex].promotion_id = promotion.id;
                    lines_apply[iindex].user_promotion = user_promotion;
                    iindex += 1
                }
                // self.pos.get_order().note = val_note;
                self.pos.push_order(self.pos.get_order());
                self.pos.get_order().finalize();
                // }
                // });
            }
        },
        remove_promotion_for_lines_byrate: function (orderlines, promotion, promotion_product_lines, rate) {
            var cur_qty = 0;
            var cur_qty_bundle = 0;
            var self = this;
            var helper = new br_helper({pos: self.pos});

            for (var i = 0; i < promotion_product_lines.length; i++) {
                var line = promotion_product_lines[i][0];
                if (line.min_quantity > 0) {
                    var bundle_promoline_orderlines = orderlines.filter(function (l) {
                        return l.promotion_line_id == line.id && line.bundle_item == true
                    })
                    if (line.min_quantity * rate < bundle_promoline_orderlines.length) {
                        var bundle_to_remove = bundle_promoline_orderlines.length - line.min_quantity * rate;
                        for (var j = 0; j < bundle_to_remove; j++) {
                            var flavors = helper.get_flavor_by_menuname(bundle_promoline_orderlines[j]);
                            for (var k = 0; k < flavors.length; k++) {
                                flavors[k].promotion_id = false;
                                flavors[k].promotion_line_id = false;
                            }
                            bundle_promoline_orderlines[j].promotion_id = false;
                            bundle_promoline_orderlines[j].promotion_line_id = false;
                        }
                    }
                    var promoline_orderline = orderlines.filter(function (l) {
                        return l.promotion_line_id == line.id && line.bundle_item == false
                    })
                    if (line.min_quantity * rate < promoline_orderline.length) {
                        var to_remove = promoline_orderline.length - line.min_quantity * rate;
                        for (var j = 0; j < to_remove; j++) {
                            var flavors = helper.get_flavor_by_menuname(promoline_orderline[j]);
                            for (var k = 0; k < flavors.length; k++) {
                                flavors[k].promotion_id = false;
                                flavors[k].promotion_line_id = false;
                            }
                            promoline_orderline[j].promotion_id = false;
                            promoline_orderline[j].promotion_line_id = false;
                        }
                    }
                }

            }
        },
        // Need further explanation here, this function DOES NOT REMOVE anything (it returns a list of orderlines need to remove ??)
        remove_promotion_product_byrate: function (product_promotions, promotion, promotion_product_line, rate, user_promotion) {
            var cur_qty = 0;
            var ret_products = [];
            for (var m = 0; m < promotion_product_line.length; m++) { //Day la tung product tren line promotion
                var product_promotion = promotion_product_line[m].product_obj;
                if (product_promotion) {
                    for (var j = 0; j < product_promotions.length; j++) {
                        var line = product_promotions[j];
                        if (line.product.id == product_promotion.id) {
                            if (cur_qty < promotion_product_line[m].min_quantity * rate) {
                                cur_qty++;
                                line.rate_promotion = rate;
                                line.user_promotion = user_promotion;
                                ret_products.push(line);
                            }
                            // previously VN team development only take care for min quantity
                            if (promotion_product_line[m].min_spending > 0) {
                                line.rate_promotion = rate;
                                line.user_promotion = user_promotion;
                                ret_products.push(line);
                            }
                        }
                    }
                }
            }
            return ret_products;
        },
        apply_product_promotion: function (promotion, is_voucher, available_quota, is_unlimited_quota, user_promotion) {
            var self = this;
            var discount_promotion_product = self.pos.db.get_product_by_id(self.pos.config.discount_promotion_product_id[0]);
            var order = self.pos.get_order();
            var helper = new br_helper({pos: self.pos});
            // var validate = helper.validate_flavor();

            var errors = self.pos.get_order().check_error_status();
            if (errors) {
                var error = errors.join('\n');
                return self.pos.gui.show_popup('error', {
                    'title': 'Invalid Discount',
                    'body': error,
                });
            }
            var promotion_product_lines = helper.get_all_products_by_promotion(promotion);
            var lines = order.get_orderlines();
            var is_error = false;
            var voucher_val = $('#div_voucher').val();
            // FIXME: why don't use hash table for mapping promotion line with order line?
            // Loop throught promotion lines
            for (var i = 0; i < promotion_product_lines.length; i++) {
                var discount_value = 0;
                var promotion_product_line = promotion_product_lines[i];
                //Get min quantity and min spending quantity of promotion line
                var min_quantity = promotion_product_line[0] ? promotion_product_line[0].min_quantity : 0;
                var min_spending = promotion_product_line[0] ? promotion_product_line[0].min_spending : 0;
                if (min_quantity == 0 && min_spending == 0)   return;

                var discount = 0;
                if (promotion_product_line[0].discount) {
                    discount = promotion_product_line[0].discount > 0 ? promotion_product_line[0].discount : 0;
                }
                var discount_amount = 0;
                if (promotion_product_line[0].discount_amount) {
                    discount_amount = promotion_product_line[0].discount_amount > 0 ? promotion_product_line[0].discount_amount : 0;
                }
                var quantity = 0;
                var sum_price = 0;
                var sum_price_w_tax = 0;
                var product_promotions = [];
                //O(n*m) ??
                // Map promotion line with order lines
                for (var m = 0; m < promotion_product_line.length; m++) {
                    //Day la tung product tren line promotion
                    var promotion_line = promotion_product_line[m];
                    var product_promotion = promotion_line.product_obj;
                    if (product_promotion) {
                        for (var j = 0; j < lines.length; j++) {
                            var line = lines[j];
                            if (line.promotion_line_id === promotion_line.id  && line.product.id == product_promotion.id  && (!line.promotion_id || line.promotion_id == promotion.id)) {
                                quantity += line.quantity;
                                sum_price += line.price;
                                sum_price_w_tax += line.get_price_with_tax();
                                product_promotions.push(line);
                            }
                        }
                    }
                }
                if (quantity < min_quantity && quantity > 0) {
                    return self.pos.gui.show_popup('error', {
                        title: _t('Invalid Discount'),
                        body: _t("Select enough products to apply this discount!"),
                    });
                }
                //What is n ? what does it mean ?????
                var n = 0;
                if (min_spending > 0) {
                    if (promotion.user_quota_type == 'amount') {
                        if (sum_price > available_quota && !(promotion.is_non_sale_trans == true || promotion.is_voucher) && is_unlimited_quota == false) {
                            n = Math.floor(available_quota / min_spending);
                        }
                        else {
                            n = Math.floor(sum_price / min_spending);
                        }
                    }
                    else {
                        n = Math.floor(sum_price / min_spending);
                        if (n > available_quota && !(promotion.is_non_sale_trans == true || promotion.is_voucher) && is_unlimited_quota == false) {
                            n = available_quota;
                        }
                    }
                }
                if (min_quantity > 0) {
                    if (promotion.user_quota_type == 'amount') {
                        n = Math.floor(quantity / min_quantity);
                        if (sum_price > available_quota && !(promotion.is_non_sale_trans == true || promotion.is_voucher) && is_unlimited_quota == false) {
                            n = Math.floor(n * available_quota / sum_price);
                        }
                    }
                    else {
                        n = Math.floor(quantity / min_quantity);
                        if (n > available_quota && !(promotion.is_non_sale_trans == true || promotion.is_voucher) && is_unlimited_quota == false) {
                            n = available_quota;
                        }
                    }
                }
                if (n == 0) continue;
                if (promotion.is_non_sale_trans == true) {
                    if (min_quantity && quantity > min_quantity) {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        self.pos.gui.show_popup('error', {
                            title: _t('Invalid Discount'),
                            body: _t("Allow use promotion 1 time!"),
                        });
                        return;
                    }
                }
                //Truong hop neu dung voucher
                if (is_voucher == true) {
                    if (order.use_voucher.indexOf(voucher_val) === -1) {
                        order.use_voucher.push(voucher_val);
                        order.set_voucher(order.use_voucher);
                    }
                    //Assign voucher for each orderline bound to this promotion
                    for (var k = 0; k < product_promotions.length; k++) {
                        if (product_promotions[k].voucher.indexOf(voucher_val) == -1) {
                            product_promotions[k].voucher.push(voucher_val);
                            product_promotions[k].set_voucher(product_promotions[k].voucher);
                        }
                    }
                    self.pos.get_order().remove_current_voucher_code();
                    $('#div_voucher').val('');
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                }
                // for product without discount amount and percentage
                if (discount === 0 && discount_amount === 0){
                    var ret_product_promotions = self.remove_promotion_product_byrate(product_promotions, promotion, promotion_product_line, n, user_promotion);
                    self.distribute_price_product_promotion(ret_product_promotions, promotion_product_line, false, false, promotion, user_promotion);
                }
                if (discount_amount > 0) {
                    // Dua tren rate de remove promotion_id o orderline ko dc tinh promotion
                    var ret_product_promotions = self.remove_promotion_product_byrate(product_promotions, promotion, promotion_product_line, n, user_promotion);
                    // Tag all products that belong to promotion line
                    // var ret_product_promotions = self.remove_promotion_product_byrate(product_promotions, promotion, promotion_product_line, 99999, user_promotion);

                    self.remove_orderline_by_product_promotion(discount_promotion_product, promotion_product_line[0].id);
                    discount_value = -1 * (discount_amount * n > sum_price && sum_price || discount_amount * n);

                    //user chỉ đc dùng maximum đúng bằng amount config trong promotion
                    if ((promotion.user_quota_type == 'amount') && (promotion.is_non_sale_trans == true)) {
                        if (sum_price > available_quota && is_unlimited_quota == false) {
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            self.pos.gui.show_popup('error', {
                                title: _t('Invalid Discount'),
                                body: _t("Allow use promotion not exceed amount quota!")
                            });
                            return;
                        }
                    }
                    discount_promotion_product.product_master_id = discount_promotion_product.id;
                    self.distribute_price_product_promotion(ret_product_promotions, promotion_product_line, Math.abs(discount_value), discount, promotion, user_promotion);
                    if (promotion.is_hq_voucher == false) {
                        var discount_line = order.add_product(discount_promotion_product, {
                            price: discount_value,
                            product_promotion_id: promotion_product_line[0].id,
                            promotion_id: promotion.id,
                            voucher: [voucher_val],
                            quantity: 1,
                            product_master_id: discount_promotion_product.id,
                        });
                    } else {
                        order.set_discount_payment(voucher_val, {
                            'journal_id': promotion.payment_method,
                            'amount': n != 0 ? -discount_value / n: -discount_value ,
                            'type': 'product'
                        });
                    }
                }
                if (discount > 0) {//this is %
                    // Dua tren rate de remove promotion_id o orderline ko dc tinh promotion
                    var ret_product_promotions = self.remove_promotion_product_byrate(product_promotions, promotion, promotion_product_line, n, user_promotion);
                    // Tag all products that belong to promotion line
                    // var ret_product_promotions = self.remove_promotion_product_byrate(product_promotions, promotion, promotion_product_line, 99999, user_promotion);

                    self.remove_orderline_by_product_promotion(discount_promotion_product, promotion_product_line[0].id);
                    discount_value = -sum_price * discount / 100;

                    //user chỉ đc dùng maximum đúng bằng amount config trong promotion
                    if ((promotion.user_quota_type == 'amount') && (promotion.is_non_sale_trans == true)) {
                        if ((sum_price + discount_value) > available_quota) {
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            self.pos.gui.show_popup('error', {
                                title: _t('Invalid Discount'),
                                body: _t("Allow use promotion not exeed amount quota!"),
                            });
                            return;
                        }
                    }

                    discount_promotion_product.product_master_id = discount_promotion_product.id;
                    self.distribute_price_product_promotion(ret_product_promotions, promotion_product_line, false, discount, promotion, user_promotion);
                    if (promotion.is_hq_voucher == false) {
                        var discount_line = order.add_product(discount_promotion_product, {
                            price: n != 0 ? discount_value / n : discount_value,
                            product_promotion_id: promotion_product_line[0].id,
                            promotion_id: promotion.id,
                            voucher: [voucher_val],
                            quantity: n,
                            rate_promotion: n,
                            product_master_id: discount_promotion_product.id,
                        });
                    } else {
                        discount_value = -sum_price_w_tax * discount / 100;
                        order.set_discount_payment(voucher_val, {
                            'journal_id': promotion.payment_method,
                            'amount': n != 0 ? -discount_value / n : -discount_value,
                            'type': 'product'
                        });
                    }
                }
                //NON SALE
                if (promotion.is_non_sale_trans == true) {
                    var lines_apply = order.get_orderlines();
                    var lines = lines_apply.filter(function (x) {
                        return x.is_flavour_item == false && x.price > 0;
                    });
                    var selection_list = _.map(lines, function (line) {
                        return {
                            label: line.product.display_name + '/' + line.quantity,
                            item: line
                        };
                    });
                    self.pos.gui.show_popup('br-nonsale-popup', {
                        'title': _t('Product used/Quantity: '),
                        list: selection_list,
                        'confirm': function (val_note) {
                            var iindex = 0;
                            while (iindex < self.pos.get_order().get_orderlines().length) {
                                lines_apply[iindex].price = 0;
                                lines_apply[iindex].price_unit = 0;
                                lines_apply[iindex].price_flavor = 0;
                                lines_apply[iindex].discount_amount = 0;
                                lines_apply[iindex].non_sale = true;
                                lines_apply[iindex].promotion_id = promotion.id;
                                lines_apply[iindex].user_promotion = user_promotion;
                                iindex += 1
                            }
                            // self.pos.get_order().note = val_note;
                            self.pos.push_order(self.pos.get_order());
                            self.pos.get_order().finalize();
                        }
                    });
                }
            }
            if (is_error == false)
                self.show_home_page();

        },
        remove_orderline_by_product_promotion: function (discount_promotion_product, promotion_product_line_id) {
            var i = 0;
            var self = this;
            var order = self.pos.get_order();
            var lines = order.get_orderlines();
            while (i < lines.length) {
                if (lines[i].get_product() === discount_promotion_product && lines[i].product_promotion_id == promotion_product_line_id) {
                    order.remove_orderline_when_click_apply(lines[i]);
                    break;
                } else {
                    i++;
                }
            }
        },
        distribute_price_product_promotion: function (product_promotions, promotion_product_line, discount_amount, discount, promotion, user_promotion) {
            var self = this;
            self.helper = new br_helper({pos: self.pos});
            //TODO: remove this temp fix
            for (var i = 0; i < product_promotions.length; i++) {
                var line = product_promotions[i];
                line.promotion_id = promotion.id;
                line.product_promotion_id = promotion_product_line[0].id;
                for (var j = 0; j < line.items.length; j++) {
                    var flavour = line.items[j];
                    flavour.promotion_id = promotion.id;
                    flavour.product_promotion_id = promotion_product_line[0].id;
                }
            }
            // if(promotion.is_hq_voucher == false){
            if (discount_amount != 0) {
                var sum_price = 0;
                var flavor_lines = [];
                for (var m = 0; m < product_promotions.length; m++) {
                    var product_promotion = product_promotions[m];
                    var flavors = self.helper.get_flavor_by_menuname(product_promotion);
                    for (var k = 0; k < flavors.length; k++) {
                        sum_price += (flavors[k].price_flavor * flavors[k].quantity * flavors[k].bom_quantity);
                        flavors[k].rate_promotion = product_promotion.rate_promotion;
                        flavors[k].user_promotion = product_promotion.user_promotion;
                        flavor_lines.push(flavors[k]);
                    }
                    product_promotion.product_promotion_id = promotion_product_line[0].id;
                    product_promotion.promotion_id = promotion.id;
                }
                if (sum_price > 0) {
                    for (var k1 = 0; k1 < flavor_lines.length; k1++) {
                        if(promotion.is_hq_voucher === false){
                            flavor_lines[k1].discount_amount = (discount_amount * (flavor_lines[k1].price_flavor * (flavor_lines[k1].quantity * flavor_lines[k1].bom_quantity))) / sum_price;
                        }
                        flavor_lines[k1].promotion_id = promotion.id;
                        flavor_lines[k1].product_promotion_id = promotion_product_line[0].id;
                    }
                }
                return;
            }
            if (discount > 0) { //this is discount %
                var flavor_lines = [];
                for (var m = 0; m < product_promotions.length; m++) {
                    var product_promotion = product_promotions[m];
                    var flavors = self.helper.get_flavor_by_menuname(product_promotion);
                    for (var k = 0; k < flavors.length; k++) {
                        if(promotion.is_hq_voucher === false) {
                            flavors[k].discount_amount = (discount / 100) * flavors[k].price_flavor * (flavors[k].quantity * flavors[k].bom_quantity);
                        }
                        flavors[k].promotion_id = promotion.id;
                        flavors[k].product_promotion_id = promotion_product_line[0].id;
                        flavors[k].rate_promotion = product_promotion.rate_promotion;
                        flavors[k].user_promotion = product_promotion.user_promotion;
                    }
                    //dont distribute for menuname
                    product_promotion.product_promotion_id = promotion_product_line[0].id;
                    product_promotion.promotion_id = promotion.id;
                }
                return;
            }
            return;
            // }
        },
    });

    screens.define_action_button({
        'name': 'promotionbutton',
        'widget': PromotionButton,
        'condition': function () {
            return true;
        },
    });

    var VoucherButton = screens.ActionButtonWidget.extend({
        template: 'VoucherButton',
        init: function (parent, options) {
            var self = this;
            this._super(parent, options);
            this.lock = false;
            this.events = {
                "change #div_voucher": "doProcessVoucher",
                "keyup #div_voucher": function (e) {
                    if (e.which == 13) {
                        self.doProcessVoucher();
                    }
                }
            }
        },
        renderElement: function () {
            this._super()
        },
        doProcessVoucher: function () {
            var self = this;
            //Prevent multiple call
            if (!self.lock) {
                self.lock = true;
                var voucher_val = $('#div_voucher').val();
                if (voucher_val.length > 0) {
                    var used_vouchers = this.pos.get_order().use_voucher;
                    if (used_vouchers.indexOf(voucher_val) != -1) {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        self.lock = false;
                        return self.gui.show_popup('error', {
                            'title': 'Validation Voucher',
                            'body': 'This voucher is already used!'
                        });
                    }
                    new Model("br.config.voucher").call("get_promotion_from_voucher",
                        [voucher_val, self.pos.config.outlet_id[0]])
                        .done(function (result) {
                            //TODO: explain response params
                            if (result.length > 0) {
                                var result_pro_id = result[0];
                                var result_voucher_validation = result[1];
                                if (result_voucher_validation == false || result_voucher_validation == voucher_val) {
                                    self.render_promotion_from_voucher(result_pro_id);
                                }
//                                else {
//                                    self.gui.show_popup('textinput', {
//                                        'title': 'Validation Voucher',
//                                        'value': '',
//                                        'confirm': function (value) {
//                                            if (value == result_voucher_validation) {
//                                                self.render_promotion_from_voucher(result_pro_id);
//                                                // $('#div_voucher').val('');
//                                            }
//                                            else {
//                                                self.gui.show_popup('error', {
//                                                    'title': 'Validation Voucher',
//                                                    'body': 'Validation Code is not correct!'
//                                                });
//                                                $('#div_voucher').val('');
//                                            }
//                                        }
//                                    });
//                                }
                            }
                            self.lock = false;
                        })
                        .fail(function (err, event) {
                            event.preventDefault();
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            var err_msg = err.data.message;
                            if (err_msg == false || err_msg == undefined) {
                                err_msg = 'Can not apply voucher in Off-line mode !';
                            }
                            self.gui.show_popup('error', {
                                'title': 'Voucher',
                                'body': err_msg.replace('None', '')
                            });
                            self.lock = false;
                        });
                } else {
                    self.lock = false;
                }
            }
        },

        render_promotion_from_voucher: function (result_pro_id) {
            var self = this;
            var tip_product = self.pos.config.tip_product_id[0];
            var order = self.pos.get_order();
            var promotion = self.pos.db.get_voucher_by_id(result_pro_id);
            if (promotion) {
                var voucher_val = $('#div_voucher').val();
                if (promotion.is_hq_voucher == true) {
                    var cashregister = order.get_cashregister_by_journal(promotion.payment_method[0]);
                    if (!cashregister) {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        return self.pos.gui.show_popup('error', {
                            'title': 'Promotion Validation',
                            'body': 'Your POS is not authorized with this payment method: ' + promotion.payment_method[1] + '. Please contact HQ for detailed instruction!'
                        });
                    }
                }
                if (promotion.type_promotion == self.pos.PROMO_BILL) {
                    var lines = order.get_orderlines();
                    if (lines.length == 0) {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        return self.pos.gui.show_popup('error', {
                            'title': 'Promotion Validation',
                            'body': 'Your shopping cart is empty'
                        });
                    }
                    self.helper = new br_helper({pos: self.pos});
                    var available_bill = self.helper.check_time_bill_promotion(promotion);
                    if (available_bill[0] == true) {
                        if (self.helper.create_line_bill_promotion(promotion, false, 0, false)) {
                            if (order.use_voucher.indexOf(voucher_val) == -1) {
                                order.use_voucher.push(voucher_val);
                                order.set_voucher(order.use_voucher);
                                var orderlines = order.get_orderlines();
                                for (var i in orderlines) {
                                    var line = orderlines[i];
                                    if (line.product.id != tip_product && line.voucher.indexOf(voucher_val) == -1) {
                                        line.voucher.push(voucher_val);
                                        line.set_voucher(line.voucher);
                                    }
                                }
                                self.pos.get_order().remove_current_voucher_code();
                                $('#div_voucher').val('');
                                $('#div_voucher').attr('readonly', false);
                                $('#div_voucher').css('background-color', '');
                            }
                        }
                    }
                    else {
                        self.pos.get_order().remove_current_voucher_code();
                        $('#div_voucher').val('');
                        $('#div_voucher').attr('readonly', false);
                        $('#div_voucher').css('background-color', '');
                        self.gui.show_popup('error', {
                            'title': 'Voucher',
                            'body': available_bill[1],
                        });
                    }
                }
                else if (promotion.type_promotion === self.pos.PROMO_PRODUCT || promotion.type_promotion === self.pos.PROMO_BUNDLE) {
                    if (promotion.is_non_sale_trans == true) {
                        var menu_lines = self.pos.get_order().get_menulines();
                        if (menu_lines.length > 0) {
                            self.pos.get_order().remove_current_voucher_code();
                            $('#div_voucher').val('');
                            $('#div_voucher').attr('readonly', false);
                            $('#div_voucher').css('background-color', '');
                            return self.pos.gui.show_popup('error', {
                                title: _t('Non sale discount'),
                                body: _t('Empty shopping cart before use this discount!'),
                            });
                        }
                    }
                    this.PromotionButton = new PromotionButton(this, {pos: self.pos});
                    this.PromotionButton.render_detail_promotion(promotion, false);
                }
            } else {
                self.pos.get_order().remove_current_voucher_code();
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                return self.pos.gui.show_popup('error', {
                    'title': 'Promotion Validation',
                    'body': 'Voucher is not valid !'
                });
            }
        }
    });

    screens.define_action_button({
        'name': 'VoucherButton',
        'widget': VoucherButton,
        'condition': function () {
            return true;
        },
    });

    return {
        PromotionButton: PromotionButton,
        VoucherButton: VoucherButton,
    };

});