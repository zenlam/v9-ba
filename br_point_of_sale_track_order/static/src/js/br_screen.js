odoo.define('br_point_of_sale_track_order.screen', function (require) {
    "use strict";

    var Model = require('web.Model');
    var screens_req = require('point_of_sale.screens');
    var br_screen = require('br_point_of_sale.screen');

    screens_req.PaymentScreenWidget.include({
        renderElement: function () {
            this._super();
            var self = this;
            this.$('.back').unbind().click(function () {
                self.click_back();
                self.pos.push_to_log(self.pos.ACTIVITY_REASON.BACK);
            });
        },
    });
    br_screen.PaymentScreenWidget.include({
        validate_card_manual: function(force_validation){
            var self = this;
            self.pos.push_to_log(self.pos.ACTIVITY_REASON.CARD);
            this._super(force_validation);
        }
    });
});