odoo.define('list_view_column_invisible.column_invisible', function (require) {
    "use strict";

    var core = require('web.core');
    var formats = require('web.formats');
    var session = require('web.session');
    var list_widget_registry = core.list_widget_registry;

    list_widget_registry.get('field.monetary').include({
        // Overwrite `_format` method
        // As currently `this.options` will pass the `string` not `object`
        // It should be `object`, So normally hack this method to convert
        // `string` to `object` & it will work like a charm.
        _format: function (row_data, options) {
            //name of currency field is defined either by field attribute, in view options or we assume it is named currency_id
            var my_options = this.options;
            if (my_options) {
                my_options = my_options.replace(/'/g, '"');
                my_options = JSON.parse(my_options);
            }
            var currency_field = (my_options && my_options.currency_field) || this.currency_field || 'currency_id';
            // var currency_field = (this.options && this.options.currency_field) || this.currency_field || 'currency_id';
            var currency_id = row_data[currency_field] && row_data[currency_field].value[0];
            var currency = session.get_currency(currency_id);
            var digits_precision = this.digits || (currency && currency.digits);
            var value = formats.format_value(row_data[this.id].value || 0, {type: this.type, digits: digits_precision}, options.value_if_empty);
            if (currency) {
                if (currency.position === "after") {
                    value += '&nbsp;' + currency.symbol;
                } else {
                    value = currency.symbol + '&nbsp;' + value;
                }
            }
            return value;
        },
    });

});
