odoo.define('br_point_of_sale_track_order.popup', function (require) {
    "use strict";
    var gui = require('point_of_sale.gui');
    var PopupWidget = require('point_of_sale.popups');
    var BrDeleteOrderConfirm = PopupWidget.extend({
        template: 'BrDeleteOrderConfirm',
        init: function (parent, options) {
            var self = this;
            this.keypress_flag = false;
            this.keyboard_handler = function (event) {
                event.stopPropagation();
            };
            this._super(parent, options);
        },

        show: function (options) {
            var self = this;
            options = options || {};
            self._super(options);
            self.renderElement();
            self.$('#delete_order_remark').focus();
            this.$el.find('#delete_order_remark')[0].addEventListener('keypress', this.keyboard_handler);
            this.$el.find('#delete_order_remark')[0].addEventListener('keydown', this.keyboard_handler);
        },
        hide: function () {
            this.$el.find('#delete_order_remark')[0].removeEventListener('keypress', this.keyboard_handler);
            this.$el.find('#delete_order_remark')[0].removeEventListener('keydown', this.keyboard_handler);
            this._super();
        },
        click_confirm: function () {
            var value = this.$('#delete_order_remark').val();
            if (!value) {
                window.alert("Please fill in 'Remark' before deleting order !");
                return false;
            }
            if (this.options.confirm) {
                this.options.confirm.call(this, value);
                this.gui.close_popup();
            } else {
                window.alert("Confirm function wasn't implemented yet !");
            }
        },
        click_cancel: function () {
            this.gui.close_popup();
        }
    });
    gui.define_popup({name: 'br_delete_confirm', widget: BrDeleteOrderConfirm});

    return {
        'BrDeleteOrderConfirm': BrDeleteOrderConfirm
    }
});
