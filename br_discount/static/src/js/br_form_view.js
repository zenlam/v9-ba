odoo.define('br_discount.form_view', function (require) {

    var FormView = require('web.FormView');

    FormView.include({
        do_show: function (options) {
            if (this.model == 'br.bundle.promotion'
                && this.fields_view.fields){
                this.fields_view.fields['field_sp'] = {};
            }
            return this._super(options);
        },
        load_record: function(record) {
            if (this.model == 'br.bundle.promotion'
                && this.fields_view.fields
                && this.fields_view.fields.hasOwnProperty("field_sp")){
                delete this.fields_view.fields['field_sp']
            }
            return this._super(record);
        },
    })
});