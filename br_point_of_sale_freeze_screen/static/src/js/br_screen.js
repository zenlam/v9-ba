odoo.define('br_point_of_sale_freeze_screen.screen', function (require) {
    "use strict";
    var Model = require('web.Model');
    var Screens = require('point_of_sale.screens');
    var BRScreen = require('br_point_of_sale.screen');

    Screens.ProductCategoriesWidget.include({
        init: function (parent, options) {
            var self = this;
            this._super(parent, options);
            this.interval = this.pos.config.freeze_interval;
            this.freeze_screen();
            if (localStorage.getItem("require_pin") == "true"){
                this.pos.ready.done(function(){
                    self.freeze_render();
                });
            }
        },
        freeze_on_login: function () {
            var self = this;
            $('#start_timeout').click(function () {
                if (self.pos.user.pos_security_pin === this.previousSibling.value){
                    self.freeze_hide();
                }else{
                    alert("Security PIN fail!.")
                }
            });
        },
        freeze_hide: function () {
            localStorage.setItem("require_pin", "false");
        },
        get_cashiers: function () {
            var list = [];
            for (var i = 0; i < this.pos.users.length; i++) {
                var user = this.pos.users[i];
                if (user.role === 'manager') {
                    list.push({
                        'label': user.name,
                        'item':  user,
                    });
                }
            }
            return list;
        },
        get_cashier_name: function () {
            var self = this;
            return self.pos.cashier ? self.pos.cashier.name : self.pos.user.name;
        },
        freeze_render: function () {
            var self = this;
            self.pos.cashier_change = null;
            if (self.gui.popup_instances.hasOwnProperty("freeze")){
                self.gui.show_popup('freeze',{
                    'title': self.get_cashier_name(),
                    confirm: function(pw) {
                        if (self.pos.cashier_change){
                            if (pw !== self.pos.cashier_change.pos_security_pin){
                                alert("Incorrect Password");
                            }else {
                                self.gui.close_popup();
                                self.freeze_hide();
                                self.pos.set_cashier(self.pos.cashier_change);
                                self.chrome.widget.username.renderElement();
                                self.pos.cashier_change = null;
                            }
                        }else {
                            var user = self.pos.get_cashier();
                            if (pw !== user.pos_security_pin) {
                                alert("Incorrect Password");
                            }else {
                                self.gui.close_popup();
                                self.freeze_hide();
                            }
                        }
                    },
                    change_cashier: function () {
                        var def = new $.Deferred();
                        self.gui.popup_instances["freeze"].$el.addClass('oe_hidden');
                        self.gui.popup_instances["selection"].show({
                            title: 'Select User',
                            list: self.get_cashiers(),
                            confirm: function (user) {def.resolve(user);}
                        });

                        def.then(function (user){
                            self.pos.cashier_change = user;
                            self.gui.popup_instances["selection"].$el.addClass('oe_hidden');
                            self.gui.popup_instances["freeze"].$el.removeClass('oe_hidden');
                            self.gui.popup_instances["freeze"].$el.find(".title").text(user.name);
                            self.gui.current_popup = self.gui.popup_instances["freeze"];
                        });
                    }
                });
            }
            localStorage.setItem("require_pin", "true");
        },
        freeze_start_timeout: function () {
            var self = this;
            var timeout = self.interval * 60000;
            return setTimeout(function () {
                self.freeze_render();
            }, timeout);
        },
        freeze_register_events: function () {
            var self = this;
            var events = ["click", "mousemove", "keydown"];
            for (var i=0; i<events.length; i++){
                document.addEventListener(events[i], self.freeze_reset_timeout.bind(this), false);
            }
        },
        freeze_reset_timeout: function () {
            if (this.freeze_timeout) {
                clearTimeout(this.freeze_timeout);
            }
            this.freeze_timeout = this.freeze_start_timeout();
        },
        freeze_screen: function () {
            this.freeze_register_events();
            this.freeze_reset_timeout();
        }
    })
});