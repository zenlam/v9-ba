odoo.define('br_point_of_sale.screen', function (require) {
    "use strict";

    var core = require('web.core');
    var model_req = require('point_of_sale.models');
    var QWeb = core.qweb;
    var _t = core._t;
    var gui = require('point_of_sale.gui');
    var Model = require('web.DataModel');
    var webModel = require('web.Model');
    var screens_req = require('point_of_sale.screens');
    var br_widgets = require('br_point_of_sale.widgets');
    var formats = require('web.formats');

    var utils = require('web.utils');

    var round_di = utils.round_decimals;

    screens_req.ProductCategoriesWidget.include({
        init: function (parent, options) {
            var self = this;
            this._super(parent, options);
            this.layer_num = 1;
            this.product_cache = new screens_req.DomCache();
            this.switch_category_handler = function (event) {
                if (this.className == 'product' && this.parentElement.className.indexOf('category-list') >= 0) {
                    self.click_product_handler(this);
                    return;
                }
                self.remove_recipe();
                self.set_category(self.pos.db.get_category_by_id(Number(this.dataset.categoryId)));
                self.render_all_layer(this);
                self.category_selected_handler(this);
            };
            this.click_pos_home = function (event) {
                self.remove_recipe();
                self.reset_self_screen();
                //TruongNN
                self.set_focus_category();
            };
        },

        //Default 1 category on homepage Lay 1 con sequence smallest of root
        set_focus_category: function () {
            var db = this.pos.db;
            var ls = db.get_category_childs_ids(db.root_category_id);
            if (ls.length > 0) {
                var categories = this.el.querySelectorAll('.js-category-switch');
                for (var c = 0; c < categories.length; c++) {
                    if (categories[c].getAttribute('data-category-id') == ls[0]) {
                        $(categories[c]).trigger('click');
                        break;
                    }
                }
            }
        },

        renderElement: function () {
            var el_str = QWeb.render(this.template, {widget: this});
            var el_node = document.createElement('div');

            el_node.innerHTML = el_str;
            el_node = el_node.childNodes[1];

            if (this.el && this.el.parentNode) {
                this.el.parentNode.replaceChild(el_node, this.el);
            }

            this.el = el_node;

            var withpics = this.pos.config.iface_display_categ_images;

            var list_container = el_node.querySelector('.category-list');
            if (list_container) {
                if (!withpics) {
                    list_container.classList.add('simple');
                } else {
                    list_container.classList.remove('simple');
                }
                for (var i = 0, len = this.subcategories.length; i < len; i++) {
                    var cate_node = this.render_category(this.subcategories[i], withpics);
                    list_container.appendChild(cate_node);
                }
            }

            var buttons = el_node.querySelectorAll('.js-category-switch');
            for (var i = 0; i < buttons.length; i++) {
                buttons[i].addEventListener('click', this.switch_category_handler);
            }

            //var products = this.pos.db.get_product_by_category(this.category.id);
            //this.product_list_widget.set_product_list(products); // FIXME: this should be moved elsewhere ...

            this.el.querySelector('.searchbox input').addEventListener('keypress', this.search_handler);
            this.el.querySelector('.searchbox input').addEventListener('keydown', this.search_handler);
            this.el.querySelector('.search-clear').addEventListener('click', this.clear_search_handler);
            /* Add event*/
            this.el.querySelector('.pos-home').addEventListener('click', this.click_pos_home);
            if (this.el.querySelector('.breadcrumb-button-apply-back')) {
                //this.el.querySelector('.breadcrumb-button-apply-back').className = this.el.querySelector('.breadcrumb-button-apply-back').className.concat(' oe_hidden');
                this.el.querySelector('.breadcrumb-button-apply-back').classList.add('oe_hidden');
            }

            if (this.pos.config.iface_vkeyboard && this.chrome.widget.keyboard) {
                this.chrome.widget.keyboard.connect($(this.el.querySelector('.searchbox input')));
            }

            //TruongNN
            this.set_focus_category();
        },
        render_all_layer: function (cate_node) {
            var self = this;
            var list_container_wrap = self.el.querySelector('.categories') ? self.el.querySelector('.categories') : $('.categories')[0];
            //list_container_wrap.innerHTML = '';
            var withpics = this.pos.config.iface_display_categ_images;
            //clear category-list
            var list_cates = self.el.querySelectorAll('.category-list');
            for (var p = list_cates.length - 1; p >= 0; p--) {
                var list_cate = list_cates[p];
                if (cate_node.parentNode == list_cate) {
                    break;
                } else {
                    list_cate.remove();
                }
            }

            var list_container = document.createElement('div');
            list_container.classList.add('category-list');
            list_container.classList.add('simple');
            if (list_container_wrap) {

                if (self.exist_category(list_container_wrap, this) == false) {
                    //fill category
                    for (var i = 0, len = this.subcategories.length; i < len; i++) {
                        var cate_node = this.render_category(this.subcategories[i], withpics);
                        cate_node.className = cate_node.className.replace(' selected-category', '');
                        list_container.appendChild(cate_node);
                    }
                    //fill product
                    var product_list = self.get_product_by_category_id(self.category);
                    for (var k = 0; k < product_list.length; k++) {
                        var product_node = self.render_product(product_list[k]);

                        product_node.addEventListener('click', this.switch_category_handler);
                        list_container.appendChild(product_node);
                    }

                    //fill category list
                    if (list_container.childElementCount > 0) {
                        list_container_wrap.insertBefore(list_container, list_container_wrap.children[list_container_wrap.childElementCount - 1]);
                    }
                }
            }
            var buttons = self.el.querySelectorAll('.js-category-switch');
            buttons = buttons ? buttons : document.querySelectorAll('.js-category-switch');
            for (var i = 0; i < buttons.length; i++) {
                // SWITCH CATEGORY HANDLER
                buttons[i].addEventListener('click', this.switch_category_handler);
            }

        },

        render_category: function (category, with_image) {
            var cached = this.category_cache.get_node(category.id);
            if (!cached) {
                if (with_image) {
                    var image_url = this.get_image_url(category);
                    var category_html = QWeb.render('CategoryButton', {
                        widget: this,
                        category: category,
                        image_url: image_url,
                    });
                    category_html = _.str.trim(category_html);
                    var category_node = document.createElement('div');
                    category_node.innerHTML = category_html;
                    category_node = category_node.childNodes[0];
                } else {
                    var category_html = QWeb.render('CategorySimpleButton', {
                        widget: this,
                        category: category,
                    });
                    category_html = _.str.trim(category_html);
                    var category_node = document.createElement('div');
                    category_node.innerHTML = category_html;
                    category_node = category_node.childNodes[0];
                }
                this.category_cache.cache_node(category.id, category_node);
                return category_node;
            }
            return cached;
        },

        set_category: function (category) {
            var db = this.pos.db;
            if (!category) {
                this.category = db.get_category_by_id(db.root_category_id);
            } else {
                this.category = category;
            }
            this.breadcrumb = [];
            var ancestors_ids = db.get_category_ancestors_ids(this.category.id);
            for (var i = 1; i < ancestors_ids.length; i++) {
                //this.breadcrumb.push(db.get_category_by_id(ancestors_ids[i]));
            }
            if (this.category.id !== db.root_category_id) {
                //this.breadcrumb.push(this.category);
            }
            this.subcategories = db.get_category_by_id(db.get_category_childs_ids(this.category.id));
        },

        exist_category: function (list_container_wrap, parent_category) {
            var self = this;
            var buttons = self.el.querySelectorAll('.js-category-switch');
            buttons = buttons ? buttons : document.querySelectorAll('.js-category-switch');
            for (var i = 0; i < buttons.length; i++) {
                var category_id = buttons[i].getAttribute('data-category-id');
                for (var k = 0, len = parent_category.subcategories.length; k < len; k++) {
                    if (category_id == parent_category.subcategories[k].id) {
                        return true;
                    }
                }
            }
            return false;
        },
        get_product_by_category_id: function (category) {
            var self = this;
            var products = [];

            for (var key in self.pos.db.product_by_id) {
                var product = self.pos.db.product_by_id[key];
                if (product.pos_categ_id) {
                    if (category.id == product.pos_categ_id[0] && product.is_menu == true
                        && product.pricelist_item_ids.length && self.pos.check_price_list(product.pricelist_item_ids)) {
                        products.push(product);
                    }
                }
            }
            products = products.sort(function (a, b) {
                if (a.sequence !== b.sequence) {
                    return a.sequence - b.sequence;
                } else {
                    return a.display_name.localeCompare(b.display_name);
                }

            });

            return products;
        },
        render_product: function (product) {
            var cached = this.product_cache.get_node(product.id);
            if (!cached) {
                var image_url = this.get_product_image_url(product);
                var product_html = QWeb.render('Product', {
                    widget: this,
                    product: product,
                    image_url: this.get_product_image_url(product),
                });
                var product_node = document.createElement('div');
                product_node.innerHTML = product_html;
                product_node = product_node.childNodes[1];
                this.product_cache.cache_node(product.id, product_node);
                return product_node;
            }
            return cached;
        },
        get_product_image_url: function (product) {
            return window.location.origin + '/web/binary/image?model=product.product&field=image_medium&id=' + product.id;
        },
        click_product_handler: function (product_node) {
            var self = this;
            if (product_node.getAttribute('data-product-id')) {
                var product_id = product_node.getAttribute('data-product-id');
                var product = self.pos.db.product_by_id[product_id];
                if (product) {
                    self.pos.get_order().add_product(product);
                }
            }
        },
        reset_self_screen: function () {
            var self = this;
            if (self.hidden) {
                self.show();
            } else {
                self.reset_category();
            }
            var buttons = self.el.querySelectorAll('.js-category-switch');
            buttons = buttons ? buttons : document.querySelectorAll('.js-category-switch');
            for (var i = 0; i < buttons.length; i++) {
                buttons[i].className = buttons[i].className.replace('selected-category', '');
            }
        },
        category_selected_handler: function (cate_node) {
            if (cate_node.parentNode) {
                for (var i = 0; i < cate_node.parentElement.children.length; i++) {
                    cate_node.parentElement.children[i].className = cate_node.parentElement.children[i].className.replace(' selected-category', '');
                }
            }
            cate_node.className = cate_node.className.replace(' selected-category', '');
            cate_node.className = cate_node.className.concat(' selected-category');
        },
        perform_search: function (category, query, buy_result) {
            this.remove_recipe();
            var products;
            var breadcrumb_button_apply_back = this.el.querySelector('.breadcrumb-button-apply-back') ? this.el.querySelector('.breadcrumb-button-apply-back') : $('.breadcrumb-button-apply-back')[0];
            if (breadcrumb_button_apply_back) {
                //breadcrumb_button_apply_back.className = breadcrumb_button_apply_back.className.concat(' oe_hidden');
                breadcrumb_button_apply_back.classList.add('oe_hidden');
            }
            if (query) {
                products = this.pos.db.search_product_in_category(this.pos.db.root_category_id, query);
                if (buy_result && products.length === 1) {
                    // TODO: shouldn't load product that isn't listed in pricelist in first place ??
                    if (products[0].is_menu  && products[0].pricelist_item_ids.length && this.pos.check_price_list(products[0].pricelist_item_ids)) {
                        this.pos.get_order().add_product(products[0]);
                        //this.clear_search();
                        var products = this.pos.db.get_product_by_category(this.pos.db.root_category_id);
                        this.render_menuname(products);
                        var input = this.el.querySelector('.searchbox input');
                        input.value = '';
                        input.focus();
                    }
                } else {
                    this.render_menuname(products);
                }
            } else {
                this.reset_self_screen();


            }
        },
        render_menuname: function (products) {
            var self = this;
            var list_container_wrap = self.el.querySelector('.categories') ? self.el.querySelector('.categories') : $('.categories')[0];
            var withpics = this.pos.config.iface_display_categ_images;
            //clear category-list
            var list_cates = self.el.querySelectorAll('.category-list');
            for (var p = list_cates.length - 1; p >= 0; p--) {
                var list_cate = list_cates[p];
                list_cate.remove();
            }

            var list_container = document.createElement('div');
            list_container.classList.add('category-list');
            if (list_container_wrap) {

                if (self.exist_category(list_container_wrap, this) == false) {
                    //fill product
                    var product_list = jQuery.grep(products, function (a) {
                        return a.is_menu == true && self.pos.check_price_list(a.pricelist_item_ids);
                    });

                    for (var k = 0; k < product_list.length; k++) {
                        var product_node = self.render_product(product_list[k]);
                        product_node.addEventListener('click', this.switch_category_handler);
                        list_container.appendChild(product_node);
                    }

                    //fill category list
                    if (list_container.childElementCount > 0) {
                        list_container_wrap.insertBefore(list_container, list_container_wrap.children[list_container_wrap.childElementCount - 1]);
                    }
                }
            }

        },

        remove_recipe: function () {
            var self = this;
            var order = self.pos.get('selectedOrder');
            order.deselect_orderline();
        },

        clear_search: function () {
            var input = this.el.querySelector('.searchbox input');
            input.value = '';
            input.focus();
            this.reset_self_screen();
            this.remove_recipe();
        },
    });

    screens_req.ProductScreenWidget.include({
        show: function () {
            this._super();
            var order = this.pos.get_order();
            if (order.is_printed) {
                this.pos.gui.show_screen('receipt');
            }
        },
        start: function () {
            this._super();
            var self = this;

            if (this.action_buttons) {
                self.pos.get_order().action_buttons = this.action_buttons;
            }


            this.$('.pay').unbind('click').click(function () {
                if (self.gui.get_current_screen() !== 'payment') {
                    // validate
                    this.valid_order = true;
                    var currentOrder = self.pos.get('selectedOrder');
                    var errors = currentOrder.check_error_status();
                    if (errors) {
                        self.error(errors.join('\n'));
                        this.valid_order = false;
                        return false;
                    }
                    if (currentOrder.orderlines.models.length === 0) {
                        self.error('You should select product first to use this mode');
                        this.valid_order = false;
                        return false;
                    }
                    // self.gui.show_screen('payment');
                    currentOrder.deselect_orderline();
                }
            });

            this.item_list_widget = new br_widgets.BrItemMasterWidget(this, {});
            this.item_list_widget.replace(this.$('.product-list'));

            // Product mixin
            if (!this.item_mixin) {
                this.item_mixin = new br_widgets.ItemSelectMixin(this, {item_list_widget: this.item_list_widget});
            }
        },

    });

    var ScreenProto = screens_req.ScreenWidget.prototype;


    screens_req.ReceiptScreenWidget.include({
        show: function () {
            ScreenProto.show.call(this);
            var self = this;

            this.render_change();
            this.render_receipt();
            var order = this.pos.get_order();

            if (this.should_auto_print()) {
                // if(!order.is_printed) {
                this.print();
                // }
                if (this.should_close_immediately()) {
                    this.click_next();
                }
            } else {
                this.lock_screen(false);
            }

        },
        check_exist_product: function (line, orderlines) {
            for (var j = 0; j < orderlines.length; j++) {
                if (!line.parent_line && !orderlines[j].parent_line) {
                    if (line.product.id == orderlines[j].product.id && line.price == orderlines[j].price) {
                        return j
                    }
                }
            }
            return -1
        },
        // render_receipt: function () {
        //     var self = this;
        //     var order = this.pos.get_order();
        //     var orderlines = order.get_orderlines();
        //
        //     var promotion_products = [
        //         self.pos.config.discount_product_id[0],
        //         self.pos.config.discount_promotion_bundle_id[0],
        //         self.pos.config.discount_promotion_product_id[0]
        //     ];
        //
        //     var receipt_lines = {};
        //     var key = function(line){
        //         // Group all menu name with same flavour
        //         var ids = [line.product.id];
        //         for(var i =0; i< line.items.length; i++){
        //             var item = line.items[i];
        //             ids.push(item.product.id);
        //         }
        //         return ids.join("|");
        //     };
        //     for(var i = 0; i < orderlines.length; i++){
        //         var line = orderlines[i];
        //         var product = line.product;
        //         if(line.show_in_cart){
        //             if(!line.parent_line){
        //                 var k = key(line);
        //                 line.display_qty = parseInt(line.quantity);
        //                 if(!(k in receipt_lines)) {
        //                     if(promotion_products.indexOf(product.id) != -1){
        //                         //Get key from closest menu name parent
        //                         var promo_key = key(parent) + product.id.toString() + i.toString();
        //                         receipt_lines[promo_key] = {
        //                             'master': {
        //                                 'display_name': line.get_display_name(),
        //                                 'display_qty': line.display_qty,
        //                                 'total': line.price * line.display_qty,
        //                                 'price': line.price,
        //                                 'tax_code': line.get_taxes_code()
        //                             },
        //                             'childs': {}
        //                         }
        //                     }else{
        //
        //                         receipt_lines[k] = {
        //                             'master': {
        //                                 'display_name': line.get_display_name(),
        //                                 'display_qty': line.display_qty,
        //                                 'total': (line.price * line.display_qty),
        //                                 'price': line.price,
        //                                 'tax_code': line.get_taxes_code()
        //                             },
        //                             'childs': {}
        //                         }
        //                     }
        //                 }else{
        //                     receipt_lines[k]['master'].display_qty += parseInt(line.quantity)
        //                 }
        //             }else{
        //                 var parent = line.parent_line;
        //                 var bom_line = self.pos.db.get_bom_line_by_line_id(line.bom_line_id);
        //                 if(!(product.id in receipt_lines[key(parent)]['childs'])){
        //                     receipt_lines[key(parent)]['childs'][product.id] = {
        //                         'child': true,
        //                         'category_sequence': bom_line.sequence,
        //                         'category_name': bom_line.name,
        //                         'display_name': line.get_display_name(),
        //                         'quantity': parseInt(line.quantity)
        //                     };
        //                 }else{
        //                     receipt_lines[key(parent)]['childs'][product.id]['quantity'] += parseInt(line.quantity);
        //                 }
        //             }
        //         }
        //     }
        //
        //     var print_lines = [];
        //     for(var k in receipt_lines){
        //         var master = receipt_lines[k]['master'];
        //         var childs = receipt_lines[k]['childs'];
        //
        //         print_lines.push(master);
        //         var arr = [];
        //         for(var x in childs){
        //             arr.push([childs[x]['category_sequence'], childs[x]['display_name'], childs[x]])
        //         }
        //         arr.sort(function(a, b){
        //             if(a[0] != b[0]){
        //                 return a[0] > b[0];
        //             }else{
        //                 if(a[1] > b[1]){
        //                     return a[1] > b[1];
        //                 }
        //             }
        //
        //         });
        //         for(var c = 0; c < arr.length; c++){
        //             print_lines.push(arr[c][2]);
        //         }
        //     }
        //     // for (var i = 0; i < orderlines.length; i++) {
        //     //     var line = orderlines[i];
        //     //     var exit_line = this.check_exist_product(line, orderlines);
        //     //     if (exit_line != -1) {
        //     //         if (orderlines[exit_line].display_qty) {
        //     //             orderlines[exit_line].display_qty += parseInt(line.quantity)
        //     //         }
        //     //         else {
        //     //             orderlines[exit_line].display_qty = parseInt(line.quantity)
        //     //         }
        //     //
        //     //     } else {
        //     //         line.display_qty = parseInt(line.quantity)
        //     //
        //     //     }
        //     //
        //     // }
        //
        //     // order.is_printed = true;
        //     //
        //     // order.save_to_db();
        //     this.$('.pos-receipt-container').html(QWeb.render('PosTicket', {
        //         widget: this,
        //         order: order,
        //         receipt: order.export_for_printing(),
        //         orderlines: orderlines,
        //         print_lines: print_lines,
        //         paymentlines: order.get_paymentlines(),
        //     }));
        // },
        render_receipt: function () {
            var order = this.pos.get_order();
            var orderlines = order.get_orderlines();

            if (!order._printed) {
                for (var i = 0; i < orderlines.length; i++) {
                    var line = orderlines[i];
                    var product = line.product;
                    var exit_line = this.check_exist_product(line, orderlines);
                    if (exit_line != -1) {
                        if (orderlines[exit_line].display_qty) {
                            orderlines[exit_line].display_qty += parseInt(line.quantity)
                        }
                        else {
                            orderlines[exit_line].display_qty = parseInt(line.quantity)
                        }

                    } else {
                        line.display_qty = parseInt(line.quantity)

                    }

                }
            }
            this.$('.pos-receipt-container').html(QWeb.render('PosTicket', {
                widget: this,
                order: order,
                receipt: order.export_for_printing(),
                orderlines: orderlines,
                paymentlines: order.get_paymentlines(),
                round_di: round_di
            }));
        },

        click_next: function () {
            this.pos.get_order().finalize();
            $('.button.back.promotion').trigger('click');
        },
        print: function () {
            var self = this;

            if (!this.pos.config.iface_print_via_proxy) { // browser (html) printing

                // The problem is that in chrome the print() is asynchronous and doesn't
                // execute until all rpc are finished. So it conflicts with the rpc used
                // to send the orders to the backend, and the user is able to go to the next
                // screen before the printing dialog is opened. The problem is that what's
                // printed is whatever is in the page when the dialog is opened and not when it's called,
                // and so you end up printing the product list instead of the receipt...
                //
                // Fixing this would need a re-architecturing
                // of the code to postpone sending of orders after printing.
                //
                // But since the print dialog also blocks the other asynchronous calls, the
                // button enabling in the setTimeout() is blocked until the printing dialog is
                // closed. But the timeout has to be big enough or else it doesn't work
                // 1 seconds is the same as the default timeout for sending orders and so the dialog
                // should have appeared before the timeout... so yeah that's not ultra reliable.

                this.lock_screen(true);

                setTimeout(function () {
                    self.lock_screen(false);
                }, 1000);

                this.print_web();
            } else {    // proxy (xml) printing
                this.print_xml();
                this.lock_screen(false);
            }
        },
    });

    var PaymentScreenWidgetProto = screens_req.PaymentScreenWidget.prototype;

    screens_req.PaymentScreenWidget.include({
        init: function (parent, options) {
            this._super(parent, options);
            var self = this;

            this.keyboard_keydown_handler = function(event){
                // override base
                // to allow back space in the third party id input field
                if (!$(event.target).hasClass('third_party_id')) {
                    if (event.keyCode === 8 || event.keyCode === 46) { // Backspace and Delete
                        event.preventDefault();
                        self.keyboard_handler(event);
                    }
                }
            };

            this.keyboard_handler = function (event) {
                if (!$(event.target).hasClass('third_party_id')) {
                    var key = '';

                    if (event.type === "keypress") {
                        if (event.keyCode === 13) { // Enter
                            self._validate_order();
                        } else if (event.keyCode === 190 || // Dot
                            event.keyCode === 110 ||  // Decimal point (numpad)
                            event.keyCode === 188 ||  // Comma
                            event.keyCode === 46) {  // Numpad dot
                            key = self.decimal_point;
                        } else if (event.keyCode >= 48 && event.keyCode <= 57) { // Numbers
                            key = '' + (event.keyCode - 48);
                        } else if (event.keyCode === 45) { // Minus
                            key = '-';
                        } else if (event.keyCode === 43) { // Plus
                            key = '+';
                        }
                    } else { // keyup/keydown
                        if (event.keyCode === 46) { // Delete
                            key = 'CLEAR';
                        } else if (event.keyCode === 8) { // Backspace
                            key = 'BACKSPACE';
                        }
                    }
                    self.payment_input(key);
                    event.preventDefault();
                }
            };
            this.msg_close_transaction = this.get_msg_close_transaction();
            this.posDisplay = window.br_socket.POSDisplay('POS Display Payment');
        },
        click_numpad: function (button) {
            if (!this.check_open_payment()) {
                return this.gui.show_popup('error', {
                    title: _t('Warning'),
                    body: _t('Please Select A Payment Method First !'),
                });
            }
            this._super(button)
        },
        check_open_payment: function () {
            var paymentlines = this.pos.get_order().get_paymentlines();
            var open_paymentline = false;

            for (var i = 0; i < paymentlines.length; i++) {
                if (!paymentlines[i].paid) {
                    open_paymentline = true;
                }
            }

            return open_paymentline;
        },
        remove_rounding_payment: function () {
            var lines = this.pos.get_order().get_paymentlines();
            for (var i = 0; i < lines.length; i++) {
                if (lines[i].cashregister == this.pos.rounding_cashregister) {
                    this.pos.get_order().remove_paymentline(lines[i]);
                    this.reset_input();
                    this.render_paymentlines();
                    return;
                }
            }
        },
        check_have_bank_payment: function () {
            var lines = this.pos.get_order().get_paymentlines();
            for (var i = 0; i < lines.length; i++) {
                if (lines[i].cashregister.journal.type === 'bank') {
                    return true;
                }
            }
            return false;
        },
        show: function () {
            this._super();
            var order = this.pos.get_order();
            $('.numpad').css("pointer-events","auto").css('opacity',1.0);
            var paymentLines = order.get_paymentlines();
            // do not remove payment line if there is any QR paymentline
            if (paymentLines.every(line => line.unique_transaction_number == false)){
                order.removeAllPaymentLines();
            }

            if (this.pos.rounding_cashregister) {
                order.add_rounding_payment(this.pos.rounding_cashregister);
            }
            this.reset_input();
            this.render_paymentlines();
            this.order_changes();
            window.document.body.addEventListener('keypress', this.keyboard_handler);
            window.document.body.addEventListener('keydown', this.keyboard_keydown_handler);

        },
        get_msg_close_transaction: function () {
            // var msg = module.POS_CONFIG_SETTINGS.close_transaction;
            // if (!msg) {
            //LongDT: Close transaction message configuration isn't coded yet
            var msg = 'Welcome to Baskin Robbins !';
            // var msg = 'Receive receipt, please. Thank you!';
            // }
            return msg;
        },
        render_paymentlines: function () {
            var self = this;
            var order = this.pos.get_order();
            if (!order) {
                return;
            }

            var lines = order.get_paymentlines();
            for (var i = 0; i < lines.length; i++) {
                var due = order.get_due(lines[i]);
                if (lines[i].cashregister.journal.type === 'bank' && lines[i].get_amount() > due) {
                    lines[i].set_amount(due);
                }
            }
            var due = order.get_due();
            var extradue = 0;
            if (due && lines.length && due !== order.get_due(lines[lines.length - 1])) {
                extradue = due;
            }


            this.$('.paymentlines-container').empty();
            var lines = $(QWeb.render('PaymentScreen-Paymentlines', {
                widget: this,
                order: order,
                paymentlines: lines,
                extradue: extradue,
            }));

            lines.on('click', '.delete-button', function () {
                self.click_delete_paymentline($(this).data('cid'));
            });

            lines.on('click', '.paymentline', function () {
                self.click_paymentline($(this).data('cid'));
            });

            lines.appendTo(this.$('.paymentlines-container'));
            if (order.get_total_with_tax() > 0) {
                this.posDisplay.displayPayment(order.get_total_with_tax(), 0, 0, order.get_total_paid(), order.get_change());
            }
        },
        _check_session_closed: function () {
            if (this.pos.get_order()) {
                var order = this.pos.get_order();
                var session_id = order.session_id;
                new webModel("pos.config").call("check_close_session",
                    [session_id],
                    undefined,
                    {
                        timeout: 3000
                    }
                ).done(function (result) {
                    return result;
                }).fail(function (error, event) {
                    return false;
                });
            }
            return false;
        },
        _validate_order: function (force_validation) {
            var self = this;
            var session_id = self.pos.pos_session.id;
            new webModel("pos.session").call("check_close_session",
                [session_id],
                undefined,
                {
                    timeout: 3000
                }
            ).then(function (result) {
                if (result == true) {
                    return self.gui.show_popup('br-error', {
                        auto_close: true,
                        message: _t('Please key in this transaction again once you open new session!')
                    });
                } else {
                    var order = self.pos.get_order();
                    // BR-765 check 3rd party transaction ID
                    var paymentLines = order.get_paymentlines();
                    var third_party_id = $('#third_party_id').val();
                    var check_transaction_id = false;
                    for (var i = 0; i < paymentLines.length; i++) {
                        if (paymentLines[i].cashregister.journal.is_required_thirdparty) {
                            if (third_party_id.trim() === '') { // trim to avoid user only enter space
                                return self.gui.show_popup('error', {
                                    'title': 'Warning',
                                    'body': 'Please Enter Third Party Transaction ID to Proceed with Payment!'
                                });
                            }
                        }
                    }
                    var req = self.make_card_payment(order, force_validation);
                    return req.then(function () {
                        //proceed and show receipt
                        order.initialize_validation_date();
                        PaymentScreenWidgetProto.validate_order.call(self, force_validation);
                    }).fail(function () {
                        // self.posDisplay.displayText(self.msg_close_transaction);
                    });
                }
                //Longdt: Is this needed ?
            }).fail(function (error, event) {
                // if disconnected network
                // Callback from websocket doesn't have 'error' and 'event' paramter
                if (event) {
                    event.stopPropagation();
                    event.preventDefault();

                    var order = self.pos.get_order();
                    var req = self.make_card_payment(order, force_validation);
                    return req.then(function () {
                        //proceed and show receipt
                        order.initialize_validation_date();
                        PaymentScreenWidgetProto.validate_order.call(self, force_validation);

                    }).fail(function () {
                    });
                }
            });
        },
        validate_card_manual: function (force_validation) {
            var self = this;
            self.validate_order(force_validation);
        },
        make_card_payment: function (order, force_validation) {
            var done_payment = new $.Deferred(), paymentLines = order.get_paymentlines();
            var count = 0, progress = 0.1, restriction_count = 0;
            var self = this;
            var onFail = function (msg) {
                done_payment.reject();
                self.hide_loading();
                self.gui.show_popup('confirm', {
                    'title': _t('Transaction Failed'),
                    'body': _t(msg + '\nClick "Confirm" To Continue Using Card Terminal Manually?'),
                    'confirm': function () {
                        // self.validate_order(force_validation)
                        self.validate_card_manual(force_validation)
                    }
                });
            };

            // count the total of online payment applied in one transaction
            for (var i = 0; i < paymentLines.length; i++) {
                var line = paymentLines[i];
                if (line.cashregister.journal.edc_terminal){
                    if (!line.cashregister.journal.edc_terminal.startsWith('manual')){
                        count++;
                        if (!line.cashregister.journal.edc_terminal.startsWith('maybank')){
                            restriction_count++;
                        }
                    }
                }
            }

            // raise error popup if the transaction contains multiple online payments
            if (restriction_count > 1) {
                self.gui.show_popup('error', {
                    title: _t('Multiple Online Payments'),
                    body: _t("One transaction shall not have more than 1 online payment method.")
                });
                done_payment.reject();
                self.hide_loading();
            } else {
                for (var i = 0; i < paymentLines.length; i++) {
                    var line = paymentLines[i];
                    // trigger the terminal action
                    if (line.cashregister.journal.edc_terminal) {
                        var terminal_info = line.cashregister.journal.edc_terminal.split('_');
                        var terminal_name = terminal_info[0],
                            terminal_action = terminal_info[1];
                        var line_number = i;

                        // if the online payment is a manual payment method, then skip the terminal triggering
                        if (terminal_name == 'manual') {
                            continue;
                        }

                        // initialize the socket
                        var sock = window.br_socket;

                        // get terminal object based on the name
                        var terminal = sock.getTerminal(terminal_name);

                        // if the QR payment line has triggered terminal once,
                        // then perform transaction inquiry instead of ewallet
                        // sale
                        if (line.unique_transaction_number) {
                            terminal_action = 'inquiryQR'
                        }

                        var transaction_promise = null;
                        switch (terminal_action) {
                            case 'sale':
                                // if the terminal is cimb, then pass the dictionary as the parameter to the sale function
                                // otherwise, just pass the amount
                                if (terminal_name == 'cimb'){
                                    var data_dict = {
                                        'ref_no': order.invoice_no,
                                        'amount': line.get_amount(),
                                    };
                                    transaction_promise = terminal.sale(data_dict);
                                    break;
                                } else {
                                    transaction_promise = terminal.sale(line.get_amount());
                                    break;
                                }
                            case 'ewallet':
                                var data_dict = {
                                    'ref_no': order.invoice_no,
                                    'amount': line.get_amount(),
                                    'program_id': line.cashregister.journal.e_wallet_cimb_code,
                                };
                                transaction_promise = terminal.ewallet_sale(data_dict);
                                break;
                            case 'bonusPoint':
                                var data_dict = {
                                    'ref_no': order.invoice_no,
                                    'amount': line.get_amount(),
                                };
                                transaction_promise = terminal.bonus_point(data_dict);
                                break;
                            case 'inquiryQR':
                                var data_dict = {
                                    'unique_transaction_number': line.unique_transaction_number,
                                    'amount': line.get_amount(),
                                }
                                transaction_promise = terminal.inquiry_qr(data_dict);
                                break;
                            case 'redeemPoint':
                                transaction_promise = terminal.redeem_point(line.get_amount());
                                break;
                            case 'redeemValue':
                                transaction_promise = terminal.redeem_value(line.get_amount());
                                break;
                            default:
                                break;
                        }
                        if (transaction_promise !== null) {
                            transaction_promise.then(function(result){
                                // if the terminal is cimb,
                                // then populate the fields returned from the response to the bank statement line
                                if (terminal_name == 'cimb') {
                                    paymentLines[line_number].approval_no = result['approval_code'] || false;
                                    paymentLines[line_number].terminal_id = result['terminal_id'] || false;
                                    paymentLines[line_number].card_number = result['card_number'] || false;
                                    paymentLines[line_number].card_type = result['card_type'] || false;
                                    paymentLines[line_number].transaction_inv_number = result['invoice_number'] || false;
                                    paymentLines[line_number].transaction_date = result['transaction_date'] || false;
                                    paymentLines[line_number].transaction_time = result['transaction_time'] || false;
                                    paymentLines[line_number].merchant_id = result['merchant_id'] || false;
                                    paymentLines[line_number].acquirer_name = result['acquirer_name'] || false;
                                    paymentLines[line_number].acquirer_code = result['bank_code'] || false;
                                    paymentLines[line_number].settlement_batch_number = result['batch_number'] || false;
                                    // if the action perform is redeem the CIMB loyalty points,
                                    // then check if the transaction is a full redeem or partial redeem.
                                    // if it is a full redeem, proceed as it is.
                                    // if it is a partial redeem, post the remaining amount to the credit card payment method.
                                    if (terminal_action == 'bonusPoint') {
                                        // get the credit card payment method using 'cimb_sale' as edc_terminal
                                        var credit_card_journal = self.pos.cashregisters.filter(function(cashregister){
                                            return cashregister.journal.edc_terminal == 'cimb_sale'
                                        });
                                        // get the full amount of the point redemption
                                        var requestAmount = line.get_amount();
                                        // get the total amount redeemed in the transaction
                                        var redeemAmount = result['reward_redeemed_amount'] / 100 || 0;
                                        // if the redeemAmount is less than the requestAmount,
                                        // create a credit card payment line
                                        if (redeemAmount < requestAmount) {
                                            // if the final redeem amount is 0, then we can simply remove the loyalty point payment line
                                            // otherwise, set the final redeem amount to the loyalty point payment line
                                            if (redeemAmount == 0){
                                                order.remove_paymentline(paymentLines[line_number]);
                                            } else {
                                                paymentLines[line_number].set_amount(redeemAmount);
                                            }
                                            // create a credit card payment line
                                            var credit_card_paymentline = new model_req.Paymentline({}, {
                                                order: order,
                                                cashregister: credit_card_journal[0],
                                                pos: order.pos,
                                            });
                                            // get the total amount charged to the credit card using requestAmount minus the redeemAmount
                                            var amount_charged_credit = requestAmount - redeemAmount;
                                            // set the charged amount to the credit card payment line
                                            credit_card_paymentline.set_amount(amount_charged_credit);
                                            // update the credit card info to the credit payment line too
                                            credit_card_paymentline.approval_no = result['approval_code'] || false;
                                            credit_card_paymentline.terminal_id = result['terminal_id'] || false;
                                            credit_card_paymentline.card_number = result['card_number'] || false;
                                            credit_card_paymentline.card_type = result['card_type'] || false;
                                            credit_card_paymentline.transaction_inv_number = result['invoice_number'] || false;
                                            credit_card_paymentline.transaction_date = result['transaction_date'] || false;
                                            credit_card_paymentline.transaction_time = result['transaction_time'] || false;
                                            credit_card_paymentline.merchant_id = result['merchant_id'] || false;
                                            credit_card_paymentline.acquirer_name = result['acquirer_name'] || false;
                                            credit_card_paymentline.acquirer_code = result['bank_code'] || false;
                                            credit_card_paymentline.settlement_batch_number = result['batch_number'] || false;
                                            // add the credit card payment line to the order
                                            order.paymentlines.add(credit_card_paymentline);
                                        }
                                    }
                                }
                                count--;
                                if (count == 0) {
                                    self.hide_loading();
                                    done_payment.resolve();
                                }
                            }).fail(function (msg){
                                // populate the UTN to the payment line if this is a cimb ewallet sale
                                if (terminal_name == 'cimb' && terminal_action == 'ewallet') {
                                    var splitted_msg = msg.split('UTN:');
                                    msg = splitted_msg[0];
                                    var utn = splitted_msg[1];
                                    paymentLines[line_number].unique_transaction_number = utn || false;
                                }
                                done_payment.reject();
                                self.hide_loading();
                                self.gui.show_popup('confirm', {
                                    'title': _t('Transaction Failed'),
                                    'body': _t(msg + '\nClick "Confirm" To Continue Using Card Terminal Manually?'),
                                    'confirm': function () {
                                        // self.validate_order(force_validation)
                                        self.validate_card_manual(force_validation)
                                    }
                                });
                            });
                        }
                    }
                }
            }
            // setTimeout(function () {
            //     // TODO: REMOVE THIS FUNCTION OR REPLACE CONDITION WITH self.gui.has_popup()
            //     if ($('.loader').is(':visible')) {
            //         self.hide_loading();
            //         self.gui.show_popup('confirm', {
            //             'title': _t('STILL WAITING ? '),
            //             'body': _t('Click "Confirm" To Continue Using MayBank Terminal Manually !'),
            //             'confirm': function () {
            //                 self.validate_order(force_validation);
            //             },
            //         });
            //     }
            // }, 30000);
            if (count > 0) {
                //make card payment transaction and wait for response
                this.show_loading();
                self.pos.chrome.loading_message('Requesting payment from ' + terminal_name);
            } else {
                done_payment.resolve();
            }
            return done_payment;
        },
        renderElement: function () {
            this._super();
            var self = this;
            this.$('.next').unbind().click(function () {
                self._validate_order();
            });
        },
        click_back: function () {
            this.remove_tip_product();
            this.pos.get_order().removeAllPaymentLines();
            this._super();
        },
        remove_tip_product: function () {
            var order = this.pos.get_order(),
                orderlines = order.get_orderlines();
            var tip_product = this.pos.config.tip_product_id[0];
            for (var i in orderlines) {
                var line = orderlines[i];
                if (line.product.id == tip_product) {
                    order.remove_orderline(line);
                }
            }
        },
        show_loading: function () {
            $('.loader').removeClass('oe_hidden');
            $('.loader').animate({opacity: 0.7}, 200, 'swing');
        },
        hide_loading: function () {
            $('.loader').animate({opacity: 0}, 200, 'swing', function () {
                $('.loader').addClass('oe_hidden');
            });
        },
        payment_input: function (input) {
            var newbuf = this.gui.numpad_input(this.inputbuffer, input, {'firstinput': this.firstinput});

            this.firstinput = (newbuf.length === 0);

            // popup block inputs to prevent sneak editing.
            if (this.gui.has_popup()) {
                return;
            }

            if (newbuf !== this.inputbuffer) {
                this.inputbuffer = newbuf;
                var order = this.pos.get_order();
                if (order.selected_paymentline) {
                    var amount = this.inputbuffer;
                    if (this.inputbuffer !== "-") {
                        amount = formats.parse_value(this.inputbuffer, {type: "float"}, 0.0);
                    }
                    //LONGDT: bank amount shouldn't exceed due amount
                    var due = order.get_due(order.selected_paymentline);
                    if (order.selected_paymentline.cashregister.journal.type == 'bank' && amount > due) {
                        amount = due;
                    }
                    order.selected_paymentline.set_amount(amount);
                    this.order_changes();
                    this.render_paymentlines();
                    this.$('.paymentline.selected .edit').text(this.format_currency_no_symbol(amount));
                }
            }
        },
        //Override
        validate_order: function (force_validation) {

            var self = this;

            var order = this.pos.get_order();
            // BR-765 add 3rd party transaction id
            var third_party_id = $('#third_party_id').val();

            // FIXME: this check is there because the backend is unable to
            // process empty orders. This is not the right place to fix it.
            if (order.get_orderlines().length === 0) {
                this.gui.show_popup('error', {
                    'title': _t('Empty Order'),
                    'body': _t('There must be at least one product in your order before it can be validated'),
                });
                return;
            }

            var plines = order.get_paymentlines();
            for (var i = 0; i < plines.length; i++) {
                if (plines[i].get_type() === 'bank' && plines[i].get_amount() < 0) {
                    this.pos_widget.screen_selector.show_popup('error', {
                        'message': _t('Negative Bank Payment'),
                        'comment': _t('You cannot have a negative amount in a Bank payment. Use a cash payment method to return money to the customer.'),
                    });
                    return;
                }
            }

            if (!order.is_paid() || this.invoicing) {
                return;
            }

            // The exact amount must be paid if there is no cash payment method defined.
            if (Math.abs(order.get_total_with_tax() - order.get_total_paid()) > 0.00001) {
                var cash = false;
                for (var i = 0; i < this.pos.cashregisters.length; i++) {
                    cash = cash || (this.pos.cashregisters[i].journal.type === 'cash');
                }
                if (!cash) {
                    this.gui.show_popup('error', {
                        title: _t('Cannot return change without a cash payment method'),
                        body: _t('There is no cash payment method available in this point of sale to handle the change.\n\n Please pay the exact amount or add a cash payment method in the point of sale configuration'),
                    });
                    return;
                }
            }

            // if the change is too large, it's probably an input error, make the user confirm.
            if (!force_validation && (order.get_total_with_tax() * 1000 < order.get_total_paid())) {
                this.gui.show_popup('confirm', {
                    title: _t('Please Confirm Large Amount'),
                    body: _t('Are you sure that the customer wants to  pay') +
                        ' ' +
                        this.format_currency(order.get_total_paid()) +
                        ' ' +
                        _t('for an order of') +
                        ' ' +
                        this.format_currency(order.get_total_with_tax()) +
                        ' ' +
                        _t('? Clicking "Confirm" will validate the payment.'),
                    confirm: function () {
                        self.validate_order('confirm');
                    },
                });
                return;
            }

            if (order.is_paid_with_cash() && this.pos.config.iface_cashdrawer) {

                this.pos.proxy.open_cashbox();
            }
            // Longdt: Open Cashdrawer
            if (order.is_paid_with_cash()) {
                window.br_socket.openCashDrawer();
            }
            self.posDisplay.displayText(self.msg_close_transaction);
            order.initialize_validation_date();

            if (order.is_to_invoice()) {
                var startDate = order.start_time;
                var endDate = new Date();
                var seconds = (endDate.getTime() - startDate.getTime()) / 1000;
                order.time_spend = seconds / 60;
                order.third_party_id = third_party_id;
                var invoiced = this.pos.push_and_invoice_order(order);
                this.invoicing = true;

                invoiced.fail(function (error) {
                    self.invoicing = false;
                    if (error.message === 'Missing Customer') {
                        self.gui.show_popup('confirm', {
                            'title': _t('Please select the Customer'),
                            'body': _t('You need to select the customer before you can invoice an order.'),
                            confirm: function () {
                                self.gui.show_screen('clientlist');
                            },
                        });
                    } else if (error.code < 0) {        // XmlHttpRequest Errors
                        self.gui.show_popup('error', {
                            'title': _t('The order could not be sent'),
                            'body': _t('Check your internet connection and try again.'),
                        });
                    } else if (error.code === 200) {    // OpenERP Server Errors
                        self.gui.show_popup('error-traceback', {
                            'title': error.data.message || _t("Server Error"),
                            'body': error.data.debug || _t('The server encountered an error while receiving your order.'),
                        });
                    } else {                            // ???
                        self.gui.show_popup('error', {
                            'title': _t("Unknown Error"),
                            'body': _t("The order could not be sent to the server due to an unknown error"),
                        });
                    }
                });

                invoiced.done(function () {
                    self.invoicing = false;
                    order.finalize();
                });
            } else {
                var startDate = order.start_time;
                var endDate = new Date();
                var seconds = (endDate.getTime() - startDate.getTime()) / 1000;
                order.time_spend = seconds / 60;
                order.third_party_id = third_party_id;
                this.pos.push_order(order);
                this.gui.show_screen('receipt');
            }
        }
    });

    screens_req.OrderWidget.include({

        init: function (parent, options) {
            var self = this;
            this._super(parent, options);
        },
        orderline_add: function () {
            this.numpad_state.reset();
            this.renderElement('and_scroll_to_bottom');

        },
        rerender_orderline: function (order_line) {
            var node = order_line.node;
            var replacement_line = this.render_orderline(order_line);
            node.parentNode.replaceChild(replacement_line, node);
        },
        renderElement: function (scrollbottom) {
            var order = this.pos.get_order();
            if (!order) {
                return;
            }
            var orderlines = order.get_orderlines();

            var el_str = QWeb.render('OrderWidget', {widget: this, order: order, orderlines: orderlines});

            var el_node = document.createElement('div');
            el_node.innerHTML = _.str.trim(el_str);
            el_node = el_node.childNodes[0];

            var fragment = document.createDocumentFragment();

            var list_container = el_node.querySelector('.orderlines');
            for (var i = 0, len = orderlines.length; i < len; i++) {
                var orderline = this.render_orderline(orderlines[i]);
                fragment.appendChild(orderline)

            }
            if (list_container !== null) {
                list_container.appendChild(fragment);
            }
            if (this.el && this.el.parentNode) {
                this.el.parentNode.replaceChild(el_node, this.el);
            }
            this.el = el_node;
            this.update_summary();

            if (scrollbottom) {
                this.el.querySelector('.order-scroller').scrollTop = 100 * orderlines.length;
            }
        },
        update_summary: function () {
            this._super();
            var order = this.pos.get_order();
            if (!order.get_orderlines().length) {
                return;
            }
            var subtotal = order ? order.get_total_without_tax() : 0;
            this.el.querySelector('.summary .subtotal .value').textContent = this.format_currency(subtotal);

        }
    });

    screens_req.ActionpadWidget.prototype.bulkQuantity = function (quantity, _self) {
        var order = _self.pos.get_order(), order_line = order.get_selected_orderline();
        // stupid check for the present of promotion screen
        var is_applying_promo = $('.breadcrumb-button-apply').is(':visible');
        if (order_line) {
            if (!order_line.parent_line && !isNaN(quantity) && quantity) {

                for (var i = 0; i < quantity; i++) {
                    var new_order_line = order.add_product(order_line.product, {promotion__id: order_line.promotion__id, promotion_line_id: order_line.promotion_line_id});
                    for (var j = 0; j < order_line.items.length; j++) {
                        var item = $.extend(true, {}, order_line.items[j]);
                        if (!is_applying_promo) {
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
        }
        // screens_req.OrderWidget.prototype.renderElement.call(order);
        $.unblockUI();
    }

    screens_req.ActionpadWidget.prototype.startBulk = function (quantity) {
        //Separate each bulking operation into batches then run async to avoid crash

        var order = this.pos.get_order();
        var self = this;
        var BATCH_SIZE = 10;
        var qty = parseInt(quantity);

        if (qty > 1) {
            qty = qty - 1;
        }
        var wrapFunction = function (fn, context, params) {
            return function () {
                fn.apply(context, params);
            };
        }

        var createBulk = function (q) {
            $.blockUI();
            setTimeout(self.bulkQuantity, 100, q, self);
        }

        var queue = [];
        while (qty > 0) {
            if (qty > BATCH_SIZE) {
                queue.push(wrapFunction(createBulk, this, [BATCH_SIZE]))
            } else {
                queue.push(wrapFunction(createBulk, this, [qty]))
            }
            qty = qty - BATCH_SIZE;
        }
        //Don't renderElement until all is loaded

        //Is this needed to save 1 queue in order to trigger renderElement? cause we use setTimeout
        while (queue.length > 0) {
            (queue.shift())();
        }
    }

    screens_req.ActionpadWidget.include({
        renderElement: function () {
            var self = this;
            this._super();
            this.$('#bulk_quantity').blur(function () {
                var order = self.pos.get_order(), order_line = order.get_selected_orderline();
                var quantity = this.value;
                if (order_line && order_line.show_in_cart === true && quantity) {
                    self.startBulk(quantity);
                    //Empty input field when the operation completed
                    this.value = "";
                }
            });
        },
    });

    screens_req.NumpadWidget.include({
        start: function () {
            this._super();
            this.$el.find('#clear_local_storage').click(function () {
                localStorage.clear();
                location.reload();
            });
        }
    });
    return screens_req
});
