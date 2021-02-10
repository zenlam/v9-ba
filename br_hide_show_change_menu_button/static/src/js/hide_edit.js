
odoo.define('hide_edit_button.form', function (require) {
"use strict";

var core = require('web.core');
var FormView = require('web.FormView');

var _t = core._t;
var QWeb = core.qweb;

FormView.include({
    load_record: function(record) {
        this._super.apply(this,arguments);
        if(this.model=='account.invoice'){
            if(this.get_fields_values().state=='paid'){
                this.$buttons.find('.oe_form_button_edit').css({"display":"none"})
            }
            else{
                this.$buttons.find('.oe_form_button_edit').css({"display":""})
            }
        }
        else if(this.model=='purchase.order'){
            if(this.get_fields_values().state=='done'){
                this.$buttons.find('.oe_form_button_edit').css({"display":"none"})
            }
            else{
                this.$buttons.find('.oe_form_button_edit').css({"display":""})
            }
        }
        else if(this.model=='sale.order'){
            if(this.get_fields_values().state=='done'){
                this.$buttons.find('.oe_form_button_edit').css({"display":"none"})
            }
            else{
                this.$buttons.find('.oe_form_button_edit').css({"display":""})
            }
        }
        else if(this.model=='account.payment'){
            if(this.get_fields_values().state!='draft'){
                this.$buttons.find('.oe_form_button_edit').css({"display":"none"})
            }
            else{
                this.$buttons.find('.oe_form_button_edit').css({"display":""})
            }
        }
        else if(this.model=='account.voucher'){
            if(this.get_fields_values().state=='posted'){
                this.$buttons.find('.oe_form_button_edit').css({"display":"none"})
            }
            else{
                this.$buttons.find('.oe_form_button_edit').css({"display":""})
            }
        }

        }
    });
});
