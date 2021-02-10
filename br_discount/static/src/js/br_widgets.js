odoo.define('br_discount.widgets', function (require) {
    'use strict'
    var core = require('web.core');
    var QWeb = core.qweb;
    var gui = require('point_of_sale.gui');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    // TODO: This idea is boo boo, Voucher should be designed as a model, something like Orderline
    var VoucherWidget = PosBaseWidget.extend({
        template: 'VoucherWidget',
        init: function (parent, options) {
            this._super(parent, options);
            this.pos.bind('change:selectedOrder', this.bind_events, this);
            this.bind_events();
            this.updateVoucher();
        },
        bind_events: function () {
            //FIXME: This might get duplicate call cause we didn't unbind event each time call VoucherWidget
            var order = this.pos.get_order();
            order.unbind('change:use_voucher', this.updateVoucher, this);
            order.bind('change:use_voucher', this.updateVoucher, this);
            order.bind('change', this.updateVoucher, this);
            order.bind('change:orderlines', this.updateVoucher, this);
            var lines = order.orderlines;
            lines.bind('change', this.updateVoucher, this);
            lines.bind('change:status', this.updateVoucher, this);
        },
        updateVoucher: function () {
            var list_container = $('.voucher-list');
            var order = this.pos.get_order();
            //Display Voucher
            list_container.empty();
            var vouchers = this.get_vouchers();
            for (var i = 0, len = vouchers.length; i < len; i++) {
                list_container.append(this.renderVoucher(vouchers[i]))
                if (!list_container.hasClass("line")) {
                    list_container.addClass("line");
                }
            }
            if (list_container.children().length > 0) {
                list_container.prepend("Voucher(s) Applied");
            }
            //TODO: Refactor this
            // Update payment list
            for (var k in order.discount_payment) {
                if (vouchers.indexOf(k) == -1) {
                    this.remove_payment_by_voucher(k);
                }
            }
        },
        renderVoucher: function (voucher) {
            var self = this;
            var click_function = function () {
                self.close_button_click.apply(self, arguments);
            };

            var el_node = document.createElement('div');
            el_node.classList.add('voucher-block');
            el_node.innerHTML = _.str.trim(voucher);
            var button = document.createElement('div');
            button.classList.add('close-button');
            button.innerHTML = '<img height="21" src="/point_of_sale/static/src/img/backspace.png" style="cursor: pointer;" width="24">'
            button.addEventListener('click', click_function);

            el_node.appendChild(button);
            // el_node = el_node.childNodes[0];
            return el_node;
        },

        close_button_click: function (e) {
            var target = e.currentTarget,
                voucher = target.previousSibling;
            this.remove_voucher(voucher);
        },
        remove_voucher: function (voucher) {
            //Remove voucher from order
            var order = this.pos.get_order();
            var orderlines = order.get_orderlines();
            var voucher_Text = voucher.textContent || voucher;

            //Remove voucher from orderlines;
            var i = orderlines.length;
            var to_remove = [];
            while(i--){
                var line = orderlines[i];
                //There is possibility that line will be deleted when its master line is removed
                if(line){
                    var v_index = line.voucher.indexOf(voucher_Text);
                    if (v_index != -1) {
                        var line_voucher = line.voucher;
                        order.remove_orderline(line);
                        var j = line.voucher.length;
                        while(j--){
                            if(line_voucher[j] != voucher_Text && to_remove.indexOf(line_voucher[j]) == -1){
                                to_remove.push(line_voucher[j]);
                            }
                        }
                    }
                }
            }
            for(var k in to_remove){
                this.remove_voucher(to_remove[k]);
            }
            //Remove voucher from order
            var voucher_idx = order.use_voucher.indexOf(voucher_Text);
            if (voucher_idx != -1) {
                order.use_voucher.splice(voucher_idx, 1);
                order.set_voucher(order.use_voucher);
            }

            this.remove_payment_by_voucher(voucher_Text);
        },
        remove_payment_by_voucher: function (voucher_code) {
            var order = this.pos.get_order();
            if (voucher_code in order.discount_payment) {
                delete order.discount_payment[voucher_code];
            }
            order.set({'discount_payment': order.discount_payment});
        },
        get_vouchers: function () {
            var order = this.pos.get_order();
            if (order.use_voucher) {
                var used_vouchers = order.use_voucher;
                return used_vouchers;
            } else {
                return [];
            }
        }
    });
    return {
        VoucherWidget: VoucherWidget
    }
});
