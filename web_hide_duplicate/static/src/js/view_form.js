'use strict';
odoo.define('web_hide_duplicate.hide_duplicate', function (require) {

	var core = require('web.core');
    var _t = core._t;
    var ajax = require('web.ajax');
    var FormView = require('web.FormView');
    
    FormView.include({
        render_sidebar: function($node) {
        	this._super($node);
        	var self = this
        	var model_name = this.model;
        	if (	model_name != undefined &&
                    this.sidebar &&
                    this.sidebar.items &&
                    this.sidebar.items.other &&
                    this.session.uid != 1 ) {
        		
        		ajax.jsonRpc('/web/model/hide_duplicate', 'call', {
                    model: model_name,
                }).then(function(result) {
                    if (result == true){
                    	var new_items_other = _.reject(self.sidebar.items.other, function (item) {
                            return item.label === _t('Duplicate');
                        });
                    	self.sidebar.items.other = new_items_other;
                    }
                    
                });
            }
        }
    });
});
