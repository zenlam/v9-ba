odoo.define('web_onchange_hide_columns.ListView', function (require) {
    var core = require('web.core');
    var data = require('web.data');
    var DataExport = require('web.DataExport');
    var formats = require('web.formats');
    var pyeval = require('web.pyeval');
    var session = require('web.session');
    var Sidebar = require('web.Sidebar');
    var utils = require('web.utils');
    var View = require('web.View');

    var ListView = require('web.ListView');
    ListView.include({
        setup_columns: function (fields, grouped) {
            var self = this;
            _.each(this.fields_view.arch.children, function (field) {
                field.attrs.parent_values = self.get_parent_values();
            });
            var res = self._super(fields, grouped);
            // Hide all columns in editable view that are invisible
            var visibles = [];
            for(var v in self.visible_columns){
                visibles.push(self.visible_columns[v].id);
            }

            _.each(self.fields_view.arch.children, function (field) {
                if (visibles.indexOf(field.attrs.name) == -1) {
                    field.attrs.style = 'display: none';
                }else{
                    delete field.attrs.style;
                }
            });

            return res;
        },
        get_parent_values: function () {
            // Get parent values of x2many field
            var field_values = {};
            if (this.dataset.parent_view) {
                // this belongs to a parent view: add parent field if possible
                var parent_view = this.dataset.parent_view;
                var child_name = this.dataset.child_name;
                var parent_name = parent_view.get_field_desc(child_name).relation_field;
                if (parent_name) {
                    field_values = parent_view.get_fields_values();
                }
            }
            return field_values;
        }
    });
    ListView.Column.include({
        init: function (id, tag, attrs) {
            this._super(id, tag, attrs);
            this.set_parent_fields();
            this.set_tree_invisible();
        },
        set_parent_fields: function () {
            for (var attr in this.parent_values) {
                var v = this.parent_values[attr];
                this.parent_values[attr] = {value: v}
            }
        },
        set_tree_invisible: function () {
            // prioritise tree invisible definition
            if (!this.invisible && this.modifiers.invisible) {
                try{
                     if (data.compute_domain(this.modifiers.invisible, this.parent_values)) {
                        this.invisible = '1';
                    } else {
                        delete this.invisible;
                    }
                }catch(err){
                    console.log(err);
                }
            }
        }
    });
});