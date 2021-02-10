odoo.define('baskin_integration_base.models', function(require) {
    "use strict";

    var core = require('web.core');
    var QWeb = core.qweb;
    var _t = core._t;
    var models = require('point_of_sale.models');
    var Promotion = require('br_discount.br_promotion');
    var Widget = require('br_discount.widgets');
    var screens = require('point_of_sale.screens');
    var Model = require('web.Model');
    var PosDB = require('point_of_sale.DB');

    // add third parties into localStorage
    PosDB.include({
        init: function (options) {
            this.third_parties = {};
            this._super(options);
        },
        add_third_parties: function (items) {
            if (!(items instanceof Array)) {
                items = [items];
            }
            for (var i = 0, len = items.length; i < len; i++) {
                var party = items[i];
                this.third_parties[items[i].id] = party;
            }
        },
    });

    // load third party model into POS
    models.load_models({
        model: 'third.party',
        fields: ['name', 'member_code_prefix'],
        domain: [['sync_member_data', '=', true]],
        loaded: function (self, third_parties) {
            self.third_parties = third_parties;
            self.db.add_third_parties(third_parties);
        },
    });

    var _super_order = models.Order.prototype;

    models.Order = models.Order.extend({
        // add member_code, member_id, and third_party to model Order
        initialize: function (attributes, options) {
            _super_order.initialize.apply(this,arguments);
            if (options.json) {
                if (options.json.member_code) {
                    this.member_code = options.json.member_code;
                } else {
                    this.member_code = false;
                }
                if (options.json.member_name) {
                    this.member_name = options.json.member_name;
                } else {
                    this.member_name = false;
                }
                if (options.json.voucher_member_code) {
                    this.voucher_member_code = options.json.voucher_member_code;
                }
                if (options.json.member_id) {
                    this.member_id = options.json.member_id;
                } else {
                    this.member_id = false;
                }
                if (options.json.third_party) {
                    this.third_party = options.json.third_party;
                } else {
                    this.third_party = false;
                }
            }
        },
        // getter and setter of the fields
        get_member_id: function() {
            var self = this;
            return self.member_id;
        },
        get_member_code: function() {
            var self = this;
            return self.member_code;
        },
        get_member_name: function() {
            var self = this;
            return self.member_name;
        },
        get_voucher_member_code: function() {
            var self = this;
            return self.voucher_member_code;
        },
        get_third_party: function() {
            var self = this;
            return self.third_party;
        },
        set_member_id: function (member_id) {
            this.member_id = member_id;
            this.set({member_id: member_id});
        },
        set_member_code: function (member_code) {
            this.member_code = member_code;
            this.set({member_code: member_code});
        },
        set_member_name: function (member_name) {
            this.member_name = member_name;
            this.set({member_name: member_name});
        },
        set_voucher_member_code: function (voucher_member_code) {
            this.voucher_member_code = voucher_member_code;
            this.set({voucher_member_code: voucher_member_code});
        },
        set_third_party: function (third_party) {
            this.third_party = third_party;
            this.set({third_party: third_party});
        },
        // inherit this function to pass the fields' value
        export_as_JSON: function () {
            var json = _super_order.export_as_JSON.apply(this,arguments);
            json.member_id = this.get_member_id();
            json.member_code = this.get_member_code();
            json.member_name = this.get_member_name();
            json.third_party = this.get_third_party();
            return json;
        },
        // inherit this function to prompt a confirmation popup to remove membership code
        remove_orderline: function (line) {
            var self = this;
            _super_order.remove_orderline.call(this, line);
            var total_orderline = self.get_orderlines().length;
            if (total_orderline == 0 && self.get_member_code()) {
                self.pos.gui.show_popup('confirm', {
                    'title': _t('Remove Member Code?'),
                    'body': _t('Shopping cart is empty! Do you want to remove the membership code from this order?'),
                    'confirm': function () {
                        self.remove_member();
                        self.pos.gui.current_screen.order_widget.renderElement();
                    }
                });
            }
        },
        remove_member: function () {
            var self = this;
            this.set_member_code(false);
            this.set_member_name(false);
            this.set_member_id(false);
            this.set_third_party(false);
        },
        // if the outlet user wants to remove a payment (have UTN), prompt a
        // confirmation popup
        remove_paymentline: function(line){
            var self = this;
            if (line.unique_transaction_number) {
                var msg = 'The customer still processing the payment.\n' +
                'Please check with the customer for the status of the payment from their phone.\n' +
                'If the customer phone shows successful payment, please click on \'Validate\' button again.\n' +
                'If the customer phone shows QR code expired / payment failed, please remove the payment line and add a new payment line.'
                self.pos.gui.show_popup('confirm', {
                    'title': _t('Remove Payment Line?'),
                    'body': msg,
                    'confirm': function () {
                        _super_order.remove_paymentline.call(self, line);
                        self.pos.gui.current_screen.render_paymentlines();
                    }
                });
            } else {
                _super_order.remove_paymentline.call(this, line);
            }
        },
        // always check the new scanned member_code with the value field
        match_member_code: function (member_code, member_name) {
            var self = this;
            // pop warning message if the member code are not matched
            if (self.member_code && self.member_code != member_code) {
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                var msg = 'Membership codes does not match!\nMember: ' + self.member_name + '\nCoupon member:' + member_name;
                if (self.voucher_member_code) {
                    msg = 'Coupon/voucher codes from different members!\nSplit the transaction for different members.';
                }
                self.pos.gui.show_popup('error', {
                    title: _t('Different Membership Applied'),
                    body: _t(msg),
                });
                return false
            }
            return true
        },
        // always check the new scanned member_code with the hidden value field
        match_voucher_member_code: function (member_code, member_name) {
            var self = this;
            // pop warning message if the member code are not matched
            if (self.voucher_member_code && self.voucher_member_code != member_code) {
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.pos.gui.show_popup('error', {
                    title: _t('Different Membership Applied'),
                    body: _t('This order has voucher(s) of another member.\nKindly remove the voucher(s) if you would like to proceed the order with new member.\nVoucher Member: '
                    + self.member_name + '\nScanned Member:' + member_name || member_code),
                });
                return false
            }
            return true
        },
    });

    Promotion.VoucherButton.include({
        // change the events trigger
        init: function (parent, options) {
            var self = this;
            this._super(parent, options);
            this.events = {
                "change #div_voucher": "doProcessCode",
                "keyup #div_voucher": function (e) {
                    if (e.which == 13) {
                        self.doProcessCode();
                    }
                }
            }
        },
        // function to handle multiple call
        doProcessCode: function () {
            var self = this;
            //Prevent multiple call
            if (!self.lock) {
                self.lock = true;
                $('#div_voucher').attr('readonly', true);
                $('#div_voucher').css('background-color', 'grey');
                var code_val = $('#div_voucher').val();
                if (code_val.length > 0) {
                    self.processCode(code_val);
                } else {
                    self.lock = false;
                    $('#div_voucher').attr('readonly', false);
                    $('#div_voucher').css('background-color', '');
                }
            }
        },
        // intermediate function to handle the recognition of scanned code
        processCode: function (code_val) {
            var self = this;
            var order = self.pos.get_order();
            var third_parties = self.pos.third_parties;
            var third_party = false;
            // if the scanned code is started with any member_code_prefix of
            // third parties, then assume the scanned code is a member code
            // from the particular third party
            for (var i = 0; i < third_parties.length; i++) {
                if (code_val.startsWith(third_parties[i].member_code_prefix)) {
                    third_party = third_parties[i];
                }
            }
            // if a third party is found, get the member data from Odoo backend
            // else proceed the code as a voucher code.
            if (third_party) {
                // remove the scanned code from the textbox
                $('#div_voucher').val('');
                $('#div_voucher').attr('readonly', false);
                $('#div_voucher').css('background-color', '');
                self.lock = false;
                // get the member data from Odoo backend
                new Model("third.party.member").call("get_member_data",
                    [code_val, third_party.id])
                    .done(function (result) {
                        // popup the member information to the outlet PIC
                        if (result) {
                            var order = self.pos.get_order();
                            var msg = 'Platform: ' + third_party['name'] +
                              '\n' + 'Member Name: ' + result['name'] +
                              '\n' + 'Member Code: ' + result['code'] +
                              '\n\nClick "Confirm" To Continue.';
                            if (order.get_member_code()) {
                                msg = 'Platform: ' + third_party['name'] +
                                  '\n' + 'Member Name: ' + result['name'] +
                                  '\n' + 'Member Code: ' + result['code'] +
                                  '\n\nTwo membership codes in current transaction\nClick "Cancel" to remain 1st code, or "Confirm" to replace with 2nd code.';
                            }
                            self.gui.show_popup('confirm', {
                                'title': _t('Member Information'),
                                'body': _t(msg),
                                'confirm': function () {
                                    // do checking the new scanned code with
                                    // the member_code field
                                    if (order.get_voucher_member_code()){
                                        if (order.match_voucher_member_code(code_val, result['name'])) {
                                            order.set_member_id(result['id']);
                                            order.set_member_code(result['code']);
                                            order.set_member_name(result['name']);
                                            order.set_third_party(third_party.id);
                                        }
                                    } else {
                                        order.set_member_id(result['id']);
                                        order.set_member_code(result['code']);
                                        order.set_member_name(result['name']);
                                        order.set_third_party(third_party.id);
                                    }
                                    // render the Order Widget Screen to show
                                    // member code
                                    self.pos.gui.current_screen.order_widget.renderElement();
                                    self.pos.gui.current_screen.voucher_widget.updateVoucher();
                                }
                            });
                        }
                    })
                    .fail(function (err, event){
                        event.preventDefault();
                        var err_msg = err.data.message;
                        // if the error is due to the network issue, then allow
                        // to proceed the transaction. Else, popup Error msg
                        if (err_msg == false || err_msg == undefined || err_msg.includes('404')) {
                            var msg = 'POS is offline. You may proceed but please inform customer the points will be given after POS goes back online.'
                            + '\n' + 'Platform: ' + third_party['name']
                            + '\n' + 'Member Code:' + code_val;
                            self.gui.show_popup('confirm', {
                                'title': _t('Member Information'),
                                'body': _t(msg + '\n\nClick "Confirm" To Continue.'),
                                'confirm': function () {
                                    // Do not set member_id in this case
                                    if (order.get_voucher_member_code()){
                                        if (order.match_voucher_member_code(code_val, false)) {
                                            order.set_member_code(code_val);
                                            order.set_third_party(third_party.id);
                                        }
                                    } else {
                                        order.set_member_code(code_val);
                                        order.set_third_party(third_party.id);
                                    }
                                    self.pos.gui.current_screen.order_widget.renderElement();
                                    self.pos.gui.current_screen.voucher_widget.updateVoucher();
                                }
                            });
                        } else {
                            if (err_msg.includes('Member Not Found!')) {
                                err_msg = 'Member not found!\nRescan or manually search member\'s phone number';
                            } else if (err_msg.includes('Member Opted Out!')) {
                                err_msg = 'Member has already opted out from the Mobile Apps';
                            }
                            self.gui.show_popup('error', {
                                'title': _t('Member Error'),
                                'body': err_msg.replace('None', '')
                            });
                        }
                    });
            } else {
                self.doProcessVoucher();
            }
        },
        // override this function to do the unwrap. Will not populate member
        // in this stage (the voucher is not yet applied)
        doProcessVoucher: function () {
            var self = this;
            var order = self.pos.get_order();
            var voucher_val = $('#div_voucher').val();
            order.set_current_voucher_code(voucher_val);
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
                        'body': 'The voucher double scanned in the current transaction!'
                    });
                }
                new Model("br.config.voucher").call("get_promotion_from_voucher",
                    [voucher_val, self.pos.config.outlet_id[0]])
                    .done(function (result) {
                        //TODO: explain response params
                        if (result.length > 0) {
                            var result_pro_id = result[0];
                            var result_voucher_validation = result[1];
                            var result_member_code = result[2];
                            var result_member_name = result[3];
                            var result_voucher_shared = result[4];
                            if (result_voucher_shared == true && !order.get_member_code()) {
                                $('#div_voucher').val('');
                                $('#div_voucher').attr('readonly', false);
                                $('#div_voucher').css('background-color', '');
                                self.lock = false;
                                return self.gui.show_popup('error', {
                                    'title': 'Shared Voucher Scanned',
                                    'body': 'This is a shared voucher. Kindly scan the membership code before applying a shared voucher!'
                                });
                            }
                            if (result_member_code && result_voucher_shared == false) {
                                if (order.match_member_code(result_member_code, result_member_name)) {
                                    if (result_voucher_validation == false || result_voucher_validation == voucher_val) {
                                        $('#div_voucher').attr('readonly', true);
                                        $('#div_voucher').css('background-color', 'grey');
                                        self.render_promotion_from_voucher(result_pro_id);
                                    }
                                }
                            } else {
                                if (result_voucher_validation == false || result_voucher_validation == voucher_val) {
                                    $('#div_voucher').attr('readonly', true);
                                    $('#div_voucher').css('background-color', 'grey');
                                    self.render_promotion_from_voucher(result_pro_id);
                                }
                            }

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
                            err_msg = 'Internet Issue. Can not use coupon/voucher.\nCall IT to report issue.\nDirect customer to customer service portal.';
                        } else if (err_msg.includes('Voucher code does not exist!')){
                            err_msg = 'Member/Coupon code not found!\nRescan or manually key in code.';
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
        },
    });

    screens.ScreenWidget.include({
        barcode_discount_voucher: function(code){
            var self = this;
            if ($('#div_voucher').is('[readonly]')) {
                self.pos.gui.show_popup('error', {
                    title: _t('Another Code in Progress!'),
                    body: _t('The voucher/discount process is not completed yet\n' +
                    'Please select the related products/flavors and click on \"Apply\" ' +
                    'to complete the process or click on \"Back\" to cancel the '+
                    'previous code BEFORE scanning the next code.\n\n' +
                    'NOTE: If you cannot see the discount screen, tap on the ' +
                    'voucher textbox once and hit Enter.'),
                });
            } else {
                $('#div_voucher').focus();
                $('#div_voucher').val(code.code);
                $('#div_voucher').attr('readonly', true);
                $('#div_voucher').css('background-color', 'grey');
            }
        },

        show: function(){
            this._super();
            this.pos.barcode_reader.set_action_callback('discount_voucher', _.bind(this.barcode_discount_voucher, this));
        },
    });

    Widget.VoucherWidget.include({
        // populate the member into order when the voucher is applied
        updateVoucher: function () {
            var self = this;
            var _super = this._super.bind(this);
            var order = this.pos.get_order();
            var vouchers = this.get_vouchers();
            if (vouchers.length > 0) {
                for (var i = 0; i < vouchers.length; i++) {
                    var voucher_val = vouchers[i];
                    new Model("br.config.voucher").call("check_promotion_member",
                        [voucher_val])
                        .done(function (result) {
                            // populate the information to the order
                            if (result.length > 0) {
                                var member_code = result[0];
                                var member_id = result[1];
                                var member_name = result[2];
                                var third_party_id = result[3];
                                var shared_voucher = result[4];
                                // the result might be false in member id,
                                // so always populate the third party id
                                order.set_third_party(third_party_id);
                                if (member_code && member_id && member_name && shared_voucher == false) {
                                    if (order.match_member_code(member_code, member_name)) {
                                        order.set_member_code(member_code);
                                        order.set_member_id(member_id);
                                        order.set_member_name(member_name);
                                        if (vouchers.length > 0) {
                                            order.set_voucher_member_code(member_code);
                                        }
                                    }
                                }
                                if (self.pos.gui.current_screen.order_widget != null){
                                    self.pos.gui.current_screen.order_widget.renderElement();
                                }
                            }
                            // call the super function
                            _super();
                        })
                        .fail(function (err, event){
                            event.preventDefault();
                            _super();
                        });
                }
            }
        },
        // remove the member info if all member vouchers are removed
        remove_voucher: function (voucher) {
            var self = this;
            this._super.apply(this, arguments);
            var order = this.pos.get_order();
            var vouchers = order.use_voucher;
            // delete the voucher member code information from the order if no voucher
            if (vouchers.length == 0) {
                order.set_voucher_member_code(false);
                self.pos.gui.current_screen.order_widget.renderElement();
            }
        },
    });
});