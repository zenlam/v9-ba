odoo.define('br_discount.popups', function (require) {
    "use strict";

    var PopupWidget = require('point_of_sale.popups');
    var gui = require('point_of_sale.gui');

    //TruongNN Show Promotion list
    var SelectionPromotionPopupWidget = PopupWidget.extend({
        template: 'SelectionPromotionPopupWidget',
        show: function (options) {
            options = options || {};
            this._super(options);
            this.gui.play_sound('error');
            this.list = options.list || [];
            this.renderElement();
        },

        click_item: function (event) {
            this.gui.close_popup();
            if (this.options.confirm) {
                var index = undefined;
                var tag = $(event.target);
                while (index === undefined) {
                    index = tag.data('item-index');
                    tag = tag.parent();
                }
                var item = this.list[parseInt(index)];
                item = item ? item.item : item;
                this.options.confirm.call(self, item);
            }
        },
    });
    gui.define_popup({name: 'selection_promotion', widget: SelectionPromotionPopupWidget});

    //VanNH Show Product NON-SALE list
    var BrNonSalePopupWidget = PopupWidget.extend({
        template: 'BrNonSalePopupWidget',
        show: function (options) {
            var self = this;
            options = options || {};
            self._super(options);
            //TODO: add another sound
            // self.gui.play_sound('error');
            self.list = options.list || [];
            self.renderElement();
            self.$('input,textarea').focus();
        },

        click_confirm: function () {
            var value = this.$('input,textarea').val();
            this.gui.close_popup();
            //FIXME: DRY VIOLATION all 'confirm' functions are the same. Be a lamb and create a default one will ya ?
            if (this.options.confirm) {
                this.pos.get_order().initialize_validation_date();
                this.options.confirm.call(this, value);
            }
        },
        click_cancel: function () {
            this.pos.get_order().note = '';
            this.pos.get_order().removePromotionLines();
            this.gui.close_popup();
        }
    });
    gui.define_popup({name: 'br-nonsale-popup', widget: BrNonSalePopupWidget});

    var BrNonSaleValidationPopupWidget = BrNonSalePopupWidget.extend({
        template: 'BrNonSaleValidationPopupWidget',
        show: function (options) {
            options = options || {};
            var self = this;
            self._super(options);
            return true;
        }
    });
    gui.define_popup({name: 'br-nonsale-validation-popup', widget: BrNonSalePopupWidget});

    return {
        SelectionPromotionPopupWidget: SelectionPromotionPopupWidget,
    };

});
