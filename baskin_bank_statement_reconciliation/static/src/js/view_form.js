'use strict';
odoo.define('baskin_bank_statement_reconciliation.on_change_confirm', function (require) {

	var Dialog = require('web.Dialog');
	var core = require('web.core');
    var _t = core._t;
    var ajax = require('web.ajax');
    var FormView = require('web.FormView');
    
    FormView.include({
    	do_onchange: function(widget) {
    		this._super(widget);
    		var self = this;
			if (widget && widget.options && widget.options.on_change_msg && self && self.datarecord && self.datarecord[widget.options.trigger_field] == true){
				Dialog.confirm(this, widget.options.on_change_msg);
			}
    	},
        
    });
});