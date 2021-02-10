
odoo.define('hide_edit_button_picking.form', function (require) {
"use strict";
var core = require('web.core');
var FormView = require('web.FormView');
var _t = core._t;
var QWeb = core.qweb;
 FormView.include({
    load_record: function(record) {
        this._super.apply(this,arguments);
        if(this.model=='stock.picking')
        {
            if(this.get_fields_values().state=='processed' || this.get_fields_values().state=='transit'
            || this.get_fields_values().state=='done'){
                this.$buttons.find('.oe_form_button_edit').css({"display":"none"})
                }
            else{
                this.$buttons.find('.oe_form_button_edit').css({"display":""})
                }
                }
        }
    });
});