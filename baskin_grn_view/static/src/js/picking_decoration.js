
odoo.define('grn_view.pickinglistview', function (require) {
"use strict";

var ListView = require('web.ListView');
var pyeval = require('web.pyeval');
var session = require('web.session');

ListView.include({
    compute_decoration_classnames: function(record) {
        var classnames= '';
        var context = _.extend({}, record.attributes, {
            uid: session.uid,
            current_date: moment().format('YYYY-MM-DD'),
            current_date_picking: moment().subtract(1, 'days').format('YYYY-MM-DD 16-00-00')
            // TODO: time, datetime, relativedelta
        });

        _.each(this.decoration, function(expr, decoration) {
            if (py.PY_isTrue(py.evaluate(expr, context))) {
                classnames += ' ' + decoration.replace('decoration', 'text');
            }
        });

        return classnames;
    }
});
});
