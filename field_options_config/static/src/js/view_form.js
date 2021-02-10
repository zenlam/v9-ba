odoo.define('field_options_config.form_relational', function (require) {

    "use strict";
    var ajax = require('web.ajax');
    var core = require('web.core');
    var data = require('web.data');
    var FormRelational = require('web.form_relational');
    var FieldMany2One = core.form_widget_registry.get('many2one');
    var FieldMany2Many = core.form_widget_registry.get('many2many');

    FieldMany2One.include({
        init: function(field_manager, node) {
            this._super(field_manager, node);
            this.field_options_values = [];
            var self = this;
            var field_options_name = this.name;
            var field_options_model_name = this.view.model;
            if (field_options_name && field_options_model_name) {
                var test = ajax.jsonRpc('/web/field/options', 'call', {
                    model: field_options_model_name,
                    field: field_options_name,
                }).then(function(result) {
                    self.field_options_values = result;
                    if (self.field_options_values){
                        _.each(self.field_options_values, function(res) {
                            self.options[Object.keys(res)] = Object.values(res)[0];
                        });    
                    }
                });
            }
        },
        // render_value: function(no_recurse) {
        //     var self = this;
        //     var field_name = this.name;
        //     var model_name = this.view.model;
        //     if (field_name && model_name) {
        //         console.log("----field_options_name--->", field_name);
        //         console.log("----field_options_model_name--->", model_name);
        //             if (self.field_options_values){
        //                 _.each(self.field_options_values, function(res) {
        //                     self.options[Object.keys(res)] = Object.values(res)[0];
        //                 });    
        //             }
        //         console.log("----options--->", self.options);
                
        //             if (! self.get("value")) {
        //                 self.display_string("");
        //                 return;
        //             }
        //             var display = self.display_value["" + self.get("value")];
        //             if (display) {
        //                 self.display_string(display);
        //                 return;
        //             }
        //             if (! no_recurse) {
        //                 var dataset = new data.DataSetStatic(self, self.field.relation, self.build_context());
        //                 var def = self.alive(dataset.name_get([self.get("value")])).done(function(data) {
        //                     if (!data[0]) {
        //                         self.do_warn(_t("Render"),
        //                             _.str.sprintf(_t("No value found for the field %s for value %s"), self.field.string, self.get("value")));
        //                         return;
        //                     }
        //                     self.display_value["" + self.get("value")] = data[0][1];
        //                     self.render_value(true);
        //                 }).fail( function (data, event) {
        //                     // avoid displaying crash errors as many2One should be name_get compliant
        //                     event.preventDefault();
        //                     self.display_value["" + self.get("value")] = self.display_value_backup["" + self.get("value")];
        //                     self.render_value(true);
        //                 });
        //                 if (self.view && self.view.render_value_defs){
        //                     self.view.render_value_defs.push(def);
        //                 }
        //             }
        //     } else {
        //         this._super();
        //     }
        // },
    });

    FieldMany2Many.include({
        init: function() {
            this._super.apply(this, arguments);
//            console.log("many2many === ",this);
            this.field_options_values = [];
            var self = this;
            var field_options_name = this.name;
            var field_options_model_name = this.view.model;
            if (field_options_name && field_options_model_name) {
                var test = ajax.jsonRpc('/web/field/options', 'call', {
                    model: field_options_model_name,
                    field: field_options_name,
                }).then(function(result) {
                    self.field_options_values = result;
                    if (self.field_options_values){
                        _.each(self.field_options_values, function(res) {
                            self.options[Object.keys(res)] = Object.values(res)[0];
                        });
                    }
                });
            }
        },
    });
});