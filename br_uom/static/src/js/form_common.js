odoo.define('br_uom.form_common', function (require) {
"use strict";

var core = require('web.core');
var data = require('web.data');
var Dialog = require('web.Dialog');
var form_common = require('web.form_common');
var _t = core._t;

var ViewDialog = Dialog.extend({ // FIXME should use ViewManager
    /**
     *  options:
     *  -readonly: only applicable when not in creation mode, default to false
     * - alternative_form_view
     * - view_id
     * - write_function
     * - read_function
     * - create_function
     * - parent_view
     * - child_name
     * - form_view_options
     */
    init: function(parent, options) {
        options = options || {};
        options.dialogClass = options.dialogClass || '';
        options.dialogClass += ' o_act_window';

        this._super(parent, _.clone(options));

        this.res_model = options.res_model || null;
        this.res_id = options.res_id || null;
        this.domain = options.domain || [];
        this.context = options.context || {};
        this.options = _.extend(this.options || {}, options || {});

        this.on('closed', this, this.select);
        this.on_selected = options.on_selected || (function() {});
    },

    init_dataset: function() {
        var self = this;
        this.created_elements = [];
        this.dataset = new data.ProxyDataSet(this, this.res_model, this.context);
        this.dataset.read_function = this.options.read_function;
        this.dataset.create_function = function(data, options, sup) {
            var fct = self.options.create_function || sup;
            return fct.call(this, data, options).done(function(r) {
                self.trigger('create_completed saved', r);
                self.created_elements.push(r);
            });
        };
        this.dataset.write_function = function(id, data, options, sup) {
            var fct = self.options.write_function || sup;
            return fct.call(this, id, data, options).done(function(r) {
                self.trigger('write_completed saved', r);
            });
        };
        this.dataset.parent_view = this.options.parent_view;
        this.dataset.child_name = this.options.child_name;
    },

    select: function() {
        if (this.created_elements.length > 0) {
            this.on_selected(this.created_elements);
            this.created_elements = [];
        }
    }
});

/**
 * Create and edit dialog (displays a form view record and leave once saved)
 */
form_common.FormViewDialog.include({
    init: function(parent, options) {
        var self = this;

        var multi_select = !_.isNumber(options.res_id) && !options.disable_multiple_selection;
        var readonly = _.isNumber(options.res_id) && options.readonly;

        if(!options || !options.buttons) {
            options = options || {};
            options.buttons = [
                {text: (readonly ? _t("Close") : _t("Discard")), classes: "btn-default o_form_button_cancel", close: true, click: function() {
                    self.view_form.trigger('on_button_cancel');
                }}
            ];

            if(!readonly) {
                options.buttons.splice(0, 0, {text: _t("Save") + ((multi_select)? " " + _t(" & Close") : ""), classes: "btn-primary o_formdialog_save", click: function() { // o_formdialog_save class for web_tests!
                        self.view_form.onchanges_mutex.def.then(function() {
                            if (!self.view_form.warning_displayed) {
                                $.when(self.view_form.save()).done(function() {
                                    self.view_form.reload_mutex.exec(function() {
                                        self.trigger('record_saved');
                                        self.close();
                                    });
                                });
                            }
                        });
                    }
                });

                if(multi_select & options.res_model != 'product.supplierinfo') {
                    options.buttons.splice(1, 0, {text: _t("Save & New"), classes: "btn-primary", click: function() {
                        $.when(self.view_form.save()).done(function() {
                            self.view_form.reload_mutex.exec(function() {
                                self.view_form.on_button_new();
                            });
                        });
                    }});
                }
            }
        }

        this._super(parent, options);
    },
});

});
