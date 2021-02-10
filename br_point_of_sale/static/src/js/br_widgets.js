odoo.define('br_point_of_sale.widgets', function (require) {
    'use strict'

    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var PopupWidget = require('point_of_sale.popups');
    var screens = require('point_of_sale.screens');
    var core = require('web.core');
    var gui = require('point_of_sale.gui');
    var _t = core._t;
    var QWeb = core.qweb;
    var br_widgets = {};
    var get_product_image_url = function (product) {
        // if (product.image) {
        //     return 'data:;base64,' + product.image;
        // } else {
            return window.location.origin + '/web/binary/image?model=product.product&field=image_medium&id=' + product.id;
        // }
    };
    // Override OrderWidget
    screens.OrderWidget.include({
        bind_order_events: function () {
            this._super();
            var self = this;
            // unbind the remove function to override it
            var lines = this.pos.get('selectedOrder').orderlines;
            // lines.unbind('remove');
            // lines.bind('remove', function (line) {
            //     this.remove_orderline(line);
            // }, this);
            lines.bind('change:status', function (line) {
                this.rerender_orderline(line);
            }, this);
        },
        change_selected_order: function() {
            this._super();
            var self = this;
            var order = this.pos.get_order();
            // render the voucher widget when switching tab
            if (order) {
                if(order.pos.gui.current_screen.voucher_widget){
                    order.pos.gui.current_screen.voucher_widget.updateVoucher();
                } else if (order.pos.gui.screen_instances.products.voucher_widget) {
                    order.pos.gui.screen_instances.products.voucher_widget.updateVoucher();
                }
            }
            $('#div_voucher').val('');
            $('#div_voucher').attr('readonly', false);
            $('#div_voucher').css('background-color', '');
            var current_voucher_code = order.get_current_voucher_code();
            if (current_voucher_code) {
                $('#div_voucher').val(current_voucher_code);
                self.pos.gui.current_screen.action_buttons.VoucherButton.doProcessCode();
            }
        },
    });

    // Create error message popup
    var BrErrorPopupWidget = PopupWidget.extend({
        template: 'BrErrorPopupWidget',
        show: function (options) {
            options = options || {};
            var self = this;
            PopupWidget.prototype.show.call(this);
            $('body').append('<audio src="/point_of_sale/static/src/sounds/error.wav" autoplay="true"></audio>');
            this.message = options.message || _t('Error');
            this.comment = options.comment || '';
            this.renderElement();
            this.$('.footer .button').click(function () {
                if (options.auto_close){
                    self.gui._close();
                    self.gui.close_popup();
                }else{
                    self.gui.close_popup();
                    if (options.confirm) {
                        options.confirm.call(self);
                    }
                }
            });
        },
        close: function () {
            PopupWidget.prototype.close.call(this);
        }
    });
    gui.define_popup({name: 'br-error', widget: BrErrorPopupWidget});

    //Tao Popup login for staff meal
     // Create error message popup
     var BrLoginUserPopupWidget = PopupWidget.extend({
        template: 'BrLoginUserPopupWidget',
        show: function (options) {
            options = options || {};
            PopupWidget.prototype.show.call(this);
            this.list    = options.list    || [];
            this.password = options.password || '';
            this.renderElement();
            var self = this;
            this.$('input#txtPassword').focus(function () {
                $("input#txtPassword").attr("type","password");
            });
            self.locked = false;
            this.$('.footer .button').click(function (e) {
                var value_pass = $('#txtPassword').val();
                var value_user = $( "select.lsuser option:selected").val();
                var comment = $( "#txtComment").val();
                if( options.confirm && !self.locked){
                    self.locked = true;
                    options.confirm.call(self, value_user, value_pass).then(function(){
                        // Why there is delay here ?
                        setTimeout(function(){
                            self.pos.get_order().note = comment;
                            if(!options.need_confirm_product){
                                self.pos.push_order(self.pos.get_order());
                                self.pos.get_order().finalize();
                            }
                            self.gui.close_popup();
                        }, 300)
                    });
                }

            });
            this.$('.cancel').click(function () {
                self.pos.get_order().removePromotionLines();
                self.gui.close_popup();
            });
            this.$('#txt_br_login_search').change(function () {
                var filter = this.value;
                var select_val = '';
                $('.lsuser option').each(function(){
                    if ($(this).text().trim().toUpperCase().indexOf(filter.toUpperCase()) !=-1) {
                        $(this).show();
                        if(select_val.length==0){
                            select_val = $(this).val().trim();
                        }
                    } else {
                        $(this).hide();
                    }
                });
                $('div.br_login_content select').val(select_val);
            });
        },
        close: function () {
            PopupWidget.prototype.close.call(this);
        }
    });
    gui.define_popup({name: 'br-login-user', widget: BrLoginUserPopupWidget});

    PosBaseWidget.prototype.error = function (message, comment) {
        if (!comment) {
            return this.gui.show_popup('br-error', {message: _t(message)});
        } else {
            return this.gui.show_popup('error', {
                message: _t(message),
                comment: _t(comment)
            });
        }
    };

    // Select product widgets
    var screens = require('point_of_sale.screens');
    br_widgets.ItemSelectMixin = PosBaseWidget.extend({
        init: function (parent, options) {
            this._super(parent, options);
            this.item_list_widget = options.item_list_widget;
            this.pos.bind('change:selectedOrder', this.bind_order_events, this);
            this.bind_order_events();
        },
        bind_order_events: function () {
            var order = this.pos.get('selectedOrder');
            order.unbind('change:selected_orderline', this.selected_orderline_changed, this);
            order.bind('change:selected_orderline', this.selected_orderline_changed, this);
        },
        select_flavour_forline: function (order_line) {
            this.item_list_widget.show(order_line, {
                on_item_selected: function (items) {
                    self.hide_select_flavour();
                }
            });
        },
        hide_select_flavour: function () {
            this.item_list_widget.hide();
        },
        selected_orderline_changed: function () {
            var selected = this.pos.get('selectedOrder').get_selected_orderline();
            if (selected && selected.product_has_flavours) {
                this.select_flavour_forline(selected);
            } else {
                this.hide_select_flavour();
            }
        }
    });
    br_widgets.BrItemMasterWidget = PosBaseWidget.extend({
        template: 'BrItemMasterWidget',
        show: function (order_line, options) {
            var self = this;
            var options = options || {};
            this.order_line = order_line;
            this.product = this.order_line.get_product();

            var lines = [];
            for (var i = 0; i < this.product.product_recipe_lines.length; i++) {
                var line = this.pos.db.product_group[this.product.product_recipe_lines[i]];
                if (line.rules.length > 1 || line.is_topping === true) {
                    lines.push(line);
                }
            }
            this.product_cache = new screens.DomCache();
            this.bom = {line_ids: lines, product_id: this.product.id};
            var order = this.pos.get('selectedOrder');
            order.set_screen_data('item_master', {});
            this.renderElement();
        },
        init: function (parent, options) {
            var self = this;
            this._super(parent, options);
            this.click_reset_filter_mode = function (event) {
                var selectedTab = self.$('.tab-header.selected'), lineId = selectedTab.data('bom-line-id'), screenData = self.getScreenData(), screenData = screenData[lineId];
                screenData.current_filter = null;
                self.reRenderBomLine(self._getBomLineById(lineId));
                self.$('.product-list-filter-bar span.selected').removeClass('selected');
            };
            this.click_product_letter_filter = function (event) {
                var initial = this.dataset.initial, bomLineId = this.dataset.bomLineId, screenData = self.getScreenData(), screenData = screenData[bomLineId];
                screenData.current_filter = initial;
                self.reRenderBomLine(self._getBomLineById(bomLineId));
                self.$('.product-list-filter-bar span').each(function () {
                    if (this.dataset.initial == initial) {
                        $(this).addClass('selected');
                    } else {
                        $(this).removeClass('selected');
                    }
                });
            };
        },
        click_product_handler: function (event) {
            var self = this;
            var product = self.pos.db.get_product_by_id(event.currentTarget.dataset.productId) || self.pos.db.get_item_master_by_id(event.currentTarget.dataset.productId);
            var parentEl = event.currentTarget.parentElement;
            var messageEL = $('.item-master-message');
            messageEL = messageEL ? messageEL : $('.item-master-message');
            if (parentEl.className.indexOf('bom-line-content') >= 0) {
                var bomLineId = parseInt(parentEl.parentNode.dataset.bomLineId), bomLine = self.pos.db.get_bom_line_by_line_id(bomLineId), capacity = this.order_line.get_bom_capacity();
                var q = capacity[bomLineId] ? capacity[bomLineId] : 0;
                var price_flavor = 0
                var obj_price = self.pos.arr_lst_price.filter(function(x) {return x[0] == self.pos.config.pricelist_id[0] && x[1] == self.product.id && x[3] == product.id && x[4] == bomLineId})
                if(obj_price.length > 0){
                    price_flavor = obj_price[0][2];
                }
                else{
                    var obj_price_categ = self.pos.arr_lst_price_categ.filter(function(x) {return x[0] == self.pos.config.pricelist_id[0] && x[1] == self.product.id && x[3] == bomLine.categ_ids[bomLine.categ_ids.length - 1] && x[4] == bomLineId})
                    if(obj_price_categ.length > 0){
                        price_flavor = obj_price_categ[0][2];
                    }
                }
                //alert(price_flavor);
                if (q > 0) {
                    return self.pos.get('selectedOrder').addItemForLine(product, this.order_line, {
                        price: 0,
                        bom_line_id: bomLineId,
                        product_master_id: self.product.id,
                        is_flavour_item: true,
                        bom_quantity: event.currentTarget.parentElement.dataset.bomQty,
                        bom_uom_id: bomLine.bom_uom_id,
                        product_category_id: bomLine.categ_ids[bomLine.categ_ids.length - 1],
                        price_flavor: price_flavor
                    }, true);
                } else {
                    return self.error('Oops, you can\'t have any more ' + bomLine.name);
                }
            }
            messageEL.text('There are X scoop(s) left.');
            messageEL.attr('style', 'line-height:24px;font-size:16px;');
            this.click_product_action(product);
        },
        click_product_action: function (new_product) {
            var self = this;

            // if (new_product.to_weight && self.pos.config.iface_electronic_scale) {
            //     self.gui.set_current_screen('scale', {product: new_product});
            // } else {
            self.pos.get('selectedOrder').brAddProduct(new_product, {merge: true});
            // }
        },
        getScreenData: function () {
            return this.pos.get('selectedOrder').get_screen_data('item_master');
        },
        _getBomLineById: function (bom_line_id) {
            var self = this;
            for (var i = 0; i < self.bom.line_ids.length; i++) {
                var l = self.bom.line_ids[i];
                if (l.id == parseInt(bom_line_id)) {
                    return l;
                }
            }
        },
        render_bom_line: function (bom_line) {
            var click_function = function () {
                self.click_product_handler.apply(self, arguments);
            };
            var self = this;
            var line_rules = bom_line.rules;
            var bom_qty = bom_line.product_qty;
            var times_add = bom_line.times;
            if (typeof line_rules !== 'undefined' && line_rules instanceof Array) {
                var el_str = QWeb.render('BrBomLineWidget', {
                    widget: this,
                    bom_line: bom_line,
                    times_add: times_add,
                    bom_qty: bom_qty
                });
                var el_node = document.createElement('div');
                el_node.innerHTML = _.str.trim(el_str);
                el_node = el_node.childNodes[0];
                el_node.setAttribute('data-bom-line-id', bom_line.id);
                var bom_line_content = el_node.querySelector('.bom-line-content');
                var screen_data = self.getScreenData(), getInitial = function (n) {
                    if (typeof n != 'undefined' && n.length > 0) {
                        return n.substr(0, 1).toUpperCase();
                    }
                };
                if (!screen_data[bom_line.id]) {
                    // set list of initial if not yet ready
                    screen_data[bom_line.id] = {};
                    var initials = line_rules.reduce(function (ar, b) {
                        if (typeof b.product != 'undefined') {
                            var letter = getInitial(b.product.display_name);
                            ar[letter] = true;
                        }
                        return ar;
                    }, {});
                    var temp = [];
                    for (var l in initials) {
                        temp.push(l);
                    }
                    temp.sort(function (a, b) {
                        return a.localeCompare(b);
                    });
                    screen_data[bom_line.id].initials = temp;
                }
                screen_data = screen_data[bom_line.id];
                if (bom_line_content) {
                    var rules_len = line_rules.length, current_filter = screen_data ? screen_data.current_filter : null, products = line_rules.reduce(function (ar, b) {
                        if (typeof b.product != 'undefined') {
                            var letter = getInitial(b.product.display_name);
                            if (!current_filter) {
                                ar.push(b);
                            } else {
                                if (letter == current_filter) {
                                    ar.push(b);
                                }
                            }
                        }
                        return ar;
                    }, []);

                    if (!current_filter) {
                        //sort product alphabetically
                        // products.sort(function (a, b) {
                        //     var l1, l2;
                        //     l1 = getInitial(a.product.display_name);
                        //     l2 = getInitial(b.product.display_name);
                        //     return (l1 ? l1.localeCompare(l2) : -1);
                        // });
                    }
                    for (var p = 0, p_len = products.length; p < p_len; p++) {
                        var product_node = self.render_product(products[p].product, products[p].id);
                        product_node.addEventListener('click', click_function);
                        bom_line_content.appendChild(product_node);
                    }
                    $(bom_line_content).find('.price-tag').hide();
                }
                return el_node;
            }
            return null;
        },
        renderGroupTabs: function () {
            var self = this;
            var bomTabContainer = $('.bom-tabs-placeholder');
            if (bomTabContainer) {
                bomTabContainer.html('');
                var instruction = '';
                var selectedLine = this.pos.get('selectedOrder').get_selected_orderline();
                if (self.bom) {
                    var bom_lines = self.bom.line_ids.reduce(function (a, b) {
                        if (b.rules) {
                            a.push(b);
                        }
                        return a;
                    }, []);
                    var el_str = QWeb.render('BrBomLineTabs', {
                        widget: this,
                        bom_lines: bom_lines
                    });
                    bomTabContainer.html(el_str);
                    // add click event
                    bomTabContainer.find('.tab-header').click(function () {
                        //on click
                        var $self = $(this);
                        var bomLine = $self.data('bom-line-id');
                        $('.tab-header').removeClass('selected');
                        $self.addClass('selected');
                        for (var i = 0; i < self.bom.line_ids.length; i++) {
                            if (self.bom.line_ids[i].id == parseInt(bomLine)) {
                                self.selectBomLineByIndex(i);
                                instruction = self.bom.line_ids[i].instruction;
                                break;
                            }
                        }
                        if (instruction != '') {
                            bomTabContainer.find('.item-msg span').text(instruction);
                        } else {
                            bomTabContainer.find('.item-msg span').text('Selecting items for ' + selectedLine.get_product().display_name);
                        }
                    });
                }
                var tab_selected = bomTabContainer.find('.tab-header .selected');
                if (tab_selected) {
                    if (self.bom && self.bom.line_ids.length > 0) {
                        instruction = self.bom.line_ids[0].instruction;
                        if (instruction != '') {
                            $(bomTabContainer).find('.item-msg span').text(instruction);
                        } else {
                            $(bomTabContainer).find('.item-msg span').text('Selecting items for ' + selectedLine.get_product().display_name);
                        }
                    }
                } else {
                    $(bomTabContainer).find('.item-msg span').text('Selecting items for ' + selectedLine.get_product().display_name);
                }
            }
        },
        get_product_image_url: function (product) {
            return get_product_image_url(product);
        },
        render_product: function (product, flavour_id) {
            var self = this;
            var flavour_id = flavour_id || null;
            var cached = this.product_cache.get_node(product.id);
            if (flavour_id != null) {
                var cached = this.product_cache.get_node(product.id + '-' + flavour_id);
            }
            if (!cached) {
                var image_url = this.get_product_image_url(product);
                var product_html = QWeb.render('Product', {
                    widget: this,
                    product: product,
                    image_url: image_url
                });
                var product_node = document.createElement('div');
                product_node.innerHTML = product_html;
                product_node = product_node.childNodes[1];
                this.product_cache.cache_node(product.id + '-' + flavour_id, product_node);
                product_node.className.concat(' flavour-item');
                return product_node;
            }
            return cached;
        },
        render_product_list_filter_bar: function (bom_line) {
            var self = this;
            var el_product_filter_bar = $('.product-list-filter-bar');
            if (el_product_filter_bar) {
                el_product_filter_bar.html('');
                var screen_data = this.pos.get('selectedOrder').get_screen_data('item_master'),
                    initials = screen_data[bom_line.id].initials;
                for (var p = 0; p < initials.length; p++) {
                    var letterEL = document.createElement('span'), product_letter = initials[p];
                    letterEL.innerHTML = product_letter;
                    letterEL.setAttribute('class', 'product-letter-filter');
                    letterEL.setAttribute('data-initial', product_letter);
                    letterEL.setAttribute('data-bom-line-id', bom_line.id);
                    letterEL.addEventListener('click', self.click_product_letter_filter);
                    if (screen_data.current_filter === product_letter) {
                        //set as selected
                        letterEL.className.append(' selected');
                    }
                    el_product_filter_bar.append(letterEL);
                }
            }
        },
        reRenderBomLine: function (bom_line) {
            var elNode = this.render_bom_line(bom_line), containers = this.el.querySelectorAll('.bom-line-container');
            for (var c = 0; c < containers.length; c++) {
                var container = containers[c];
                if (parseInt(container.dataset.bomLineId) == bom_line.id) {
                    container.parentNode.replaceChild(elNode, container);
                    break;
                }
            }
        },
        selectBomLineByIndex: function (idx) {
            var self = this;
            if (self.bom) {
                var bom_line = self.bom.line_ids[idx];
                $('.bom-line-container').each(function () {
                    var c = $(this);
                    if (c.data('bom-line-id') == bom_line.id) {
                        c.removeClass('oe_hidden');
                    } else {
                        c.addClass('oe_hidden');
                    }
                });
                //next , check if it's necessary to display a header
                if (bom_line) {
                    if (bom_line.rules && bom_line.rules.length >= 20) {
                        // reload the alphabet filter
                        $('.product-list-header').removeClass('oe_hidden');
                        // update header filter
                        self.render_product_list_filter_bar(bom_line);
                    } else {
                        //$('.product-list-header').addClass('oe_hidden');
                        $('.product-list-header').removeClass('oe_hidden');
                         self.render_product_list_filter_bar(bom_line);
                    }
                }
            }
        },
        renderProductList: function () {
            var self = this;
            self.renderGroupTabs();
            var list_container = $('.product-list');
            if (list_container) {
                list_container.html('');
                //reset
                if (self.bom) {
                    var bom = self.bom;

                    // Get product list
                    var candidateIdx = -1;
                    for (var j = 0, line_len = bom.line_ids.length; j < line_len; j++) {
                        var bom_line = bom.line_ids[j];
                        var bom_line_container = self.render_bom_line(bom_line);
                        if (bom_line_container) {
                            list_container.append(bom_line_container);
                            if (candidateIdx < 0)
                                candidateIdx = j;
                        }
                    }
                    if (candidateIdx >= 0) {
                        self.selectBomLineByIndex(candidateIdx);
                    }
                }
            }
        },
        check_skip_choose_item_master: function () {
            var self = this;
            if (self.bom) {
                var choose_count = 0,
                    line_ids = self.bom.line_ids;
                for (var i = 0; i < line_ids.length; i++) {
                    if (line_ids[i].rules.length > 1 || line_ids[i].is_topping == true) {
                        choose_count++;
                    }
                }
                return choose_count != 0;
            }
            return false;
        },

        renderElement: function () {
            this._super();
            if (this.check_skip_choose_item_master()) {
                var self = this;
                var resetBtn = self.el.querySelector('.reset-filter-mode');
                if (resetBtn) {
                    resetBtn.addEventListener('click', self.click_reset_filter_mode);
                }
                if (self.bom) {
                    var selectedOrder = self.pos.get('selectedOrder');
                    self.renderProductList();
                }
            }else {
                $('.product-list-header').addClass('oe_hidden');
            }
        }
    });
    return br_widgets;
});
