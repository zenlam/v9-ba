odoo.define('web_onchange_hide_columns.FormView', function (require) {
    var core = require('web.core');
    var crash_manager = require('web.crash_manager');
    var data = require('web.data');
    var Dialog = require('web.Dialog');
    var Sidebar = require('web.Sidebar');
    var utils = require('web.utils');
    var View = require('web.View');
    var FormView = require('web.FormView');

    FormView.include({
        on_processed_onchange: function (result) {
            var self = this;
            var to_reload = [];
            // try {
            if (result && result.value && !$.isEmptyObject(result.value)) {
                var fields = this.fields;
                _.each(fields, function (field) {
                    if (field.field.type === 'one2many' && field.get_active_view) {
                        var view = field.get_active_view();
                        if (view && view.type && view.type === 'list') {
                            var controller = view.controller;
                            // Rerender x2many list view
                            if (controller.fields_view && controller.x2m) {
                                controller.load_list(controller.fields_view);
                                to_reload.push(controller);
                            }
                        }
                    }
                });
            }
            // } catch (e) {
            //     console.error(e);
            // }
            return self._super(result).then(function () {
                while (to_reload.length !== 0) {
                    var c = to_reload.pop();
                    // Padding, no ?
                    c.reload();
                }
            });
        }
    })

});