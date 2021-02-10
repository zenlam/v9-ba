'use strict';
odoo.define('notify_on_save.NotifyOnSave', function (require) {
    var FormView = require('web.FormView');

    FormView.include({
        on_button_save: function(e){
            this._super(e);
            var self = this;
            var context = self.dataset.context;
            var notify = context.notify;
            if(notify){
                self.do_notify(notify.title, notify.message);
            }
        }
    });
});