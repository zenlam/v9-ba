odoo.define('baskin_integration_mobile.chrome', function (require) {
    "use strict";

    var chrome = require('point_of_sale.chrome');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var Model = require('web.Model');
    var core = require('web.core');
    var _t = core._t;

    /* ------- Mobile Apps Button Widget ------- */

    var MobilePhoneButtonWidget = PosBaseWidget.extend({
        jsLibs: ['/baskin_integration_mobile/static/src/js/sha1.js',
        ],
        template: 'MobilePhoneButtonWidget',
        init: function(parent, options) {
            options = options || {};
            this._super(parent, options);
        },
        start: function(){
            var self = this;

            this.$el.click(function(){
                self.gui.show_popup('mobilephone', {
                    title: 'Mobile App: Phone Number',
                    confirm: function(phone_number) {
                        phone_number = '+' + phone_number.replace('(', '').replace(')', '');
                        var phone_number_hash = sha1(phone_number);
                        // get the member data from Odoo backend based on the phone number
                        new Model ("third.party.member").call("get_member_data_mobile",
                            [phone_number_hash])
                            .done(function (result) {
                                // popup the member information to the outlet PIC
                                if (result) {
                                    var order = self.pos.get_order();
                                    var third_party = _.find(self.pos.third_parties, function (third_party) {
                                        return third_party.id === result['third_party_id'];
                                    });
                                    var msg = 'Platform: ' + third_party.name
                                     + '\n' + 'Member Name: ' + result['name']
                                     + '\n' + 'Member Code: ' + result['code']
                                     + '\n\nClick Confirm To Continue.';
                                    if (order.get_member_code()) {
                                        msg = 'Platform: ' + third_party.name
                                        + '\n' + 'Member Name: ' + result['name']
                                        + '\n' + 'Member Code: ' + result['code']
                                        + '\n\nTwo membership codes in current transaction\nClick "Cancel to remain 1st code, or "Confirm" to replace with 2nd code.';
                                    }
                                    self.gui.show_popup('confirm', {
                                        'title': _t('Member Information'),
                                        'body': _t(msg),
                                        'confirm': function () {
                                            // do checking the new code with the member_code field
                                            if (order.get_voucher_member_code()){
                                                if (order.match_voucher_member_code(result['code'], result['name'])) {
                                                    order.set_member_id(result['id']);
                                                    order.set_member_code(result['code']);
                                                    order.set_member_name(result['name']);
                                                    order.set_third_party(result['third_party_id']);
                                                }
                                            } else {
                                                order.set_member_id(result['id']);
                                                order.set_member_code(result['code']);
                                                order.set_member_name(result['name']);
                                                order.set_third_party(result['third_party_id']);
                                            }
                                            // render the Order Widget Screen to show member code
                                            self.pos.gui.current_screen.order_widget.renderElement();
                                            self.pos.gui.current_screen.voucher_widget.updateVoucher();
                                        }
                                    });
                                }
                            })
                            .fail(function (err, event){
                                event.preventDefault();
                                var err_msg = err.data.message;
                                // if the error is due to the network issue or unknown error, prompt error
                                if (err_msg == false || err_msg == undefined || err_msg.includes('404')) {
                                    self.gui.show_popup('error', {
                                        'title': _t('Mobile Number'),
                                        'body': _t('Internet issue. Cannot search mobile number. \nScan membership code, instead of manual search.')
                                    })
                                } else {
                                    self.gui.show_popup('error', {
                                        'title': _t('Member Error'),
                                        'body': err_msg.replace('None', '')
                                    });
                                }
                            });
                    }
                });
            })
        },
    });

    // append the mobile app button to the top dock
    chrome.Chrome.include({
        build_widgets: function(){
            this.widgets.splice(2, 0, {
                'name':   'mobile_app_button',
                'widget': MobilePhoneButtonWidget,
                'append':  '.pos-rightheader',
            });
            this._super();
        },
    });

});
