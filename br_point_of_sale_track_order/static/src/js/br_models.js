odoo.define('br_point_of_sale_track_order.models', function (require) {
    "use strict";
    var BrModels = require('br_point_of_sale.models');
    var POSModels = require('point_of_sale.models');
    var OrderPrototype = BrModels.Order.prototype;
    var PosModelPrototype = POSModels.PosModel.prototype;

    POSModels.PosModel = POSModels.PosModel.extend({
        log_name: 'POS_offline_activity',
        initialize: function (session, attribute) {
            PosModelPrototype.initialize.call(this, session, attribute);
            this.log_name = this.log_name + "_" + new Date().getTime();
            this.tmp_log = null;
            this.ACTIVITY_REASON = {
                "DELETE": "delete",
                "BACK": "back",
                "DESTROY": "destroy",
                "CARD": "card"
            }
        },
        delete_current_order: function () {
            // Save on deleting order
            var self = this;
            self.push_to_log(self.ACTIVITY_REASON.DESTROY, false, arguments);
            PosModelPrototype.delete_current_order.call(this, arguments);

        },
        push_to_log: function (reason, lines, args) {
            // Create / Update activity
            var self = this;
            var loglines = lines;
            var current_log = self.get_activity_log();
            var log = self.get_order_log(current_log) || self.create_log(current_log, reason);

            //Add custom data
            var additional_data = {
                'date_log': new Date(),
                "cashier_id": self.cashier.id,
            };
            if(args !== undefined){
                for (var j in args) {
                    $.extend(additional_data, args[j]);
                }
            }

            if (!loglines) {
                var order = this.get_order();
                var orderlines = order.get_orderlines().filter(function (x) {
                    return !x.parent_line;
                });
                for (var i in orderlines) {
                    var line = orderlines[i];
                    var track_lines = {
                        'product_id': line.product.id,
                        'unit_price': line.price,
                        'quantity': line.quantity,
                        'reason': reason,
                    };
                    $.extend(track_lines, additional_data);
                    log['lines'].push(track_lines)
                }
            } else {
                for (var k in loglines) {
                    loglines[k]['reason'] = reason;
                    $.extend(loglines[k], additional_data);
                    log['lines'].push(loglines[k]);
                }
            }
            self.save_activity_log(current_log);
            return log;
        },
        create_log: function (current_log, reason) {
            // Create activity log
            var self = this;
            var order = this.get_order();
            var log = {
                "pos_user": self.user.id,
                "outlet_id": self.outlet.id,
                "invoice_no": order.name,
                "reference": order.name + '-' + order.activity_sequence,
                "date": order.creation_date,
                "lines": []
            };
            order.activity_sequence += 1;
            current_log.push(log);
            return log
        },
        save_activity_log: function (log) {
            var self = this;
            localStorage[self.log_name] = JSON.stringify(log);

        },
        get_activity_log: function () {
            return JSON.parse(localStorage[this.log_name] || '[]')
        },
        get_order_log: function (activity_log) {
            var order = this.get_order();
            for (var i in activity_log) {
                var log = activity_log[i];
                if (log.invoice_no == order.name) {
                    return log
                }
            }
            return false;
        }

    });

    BrModels.Order = BrModels.Order.extend({
        initialize: function (attributes, options) {
            var json = options.json;
            // set activity log sequence
            if (json) {
                this.activity_sequence = json.activity_sequence || 0;
            } else {
                this.activity_sequence = 0;
            }
            OrderPrototype.initialize.call(this, attributes, options);
        },
        remove_orderline: function (line) {
            var self = this;
            // When remove orderline save to activity log
            if (line && !line.parent_line) {
                var log_lines = [{'product_id': line.product.id, 'unit_price': line.price, 'quantity': line.quantity}];
                var val = self.pos.push_to_log(self.pos.ACTIVITY_REASON.DELETE, log_lines);
            }
            OrderPrototype.remove_orderline.call(this, line);
        },
        init_from_JSON: function (json) {
            this.activity_sequence = json.activity_sequence;
            OrderPrototype.init_from_JSON.apply(this, arguments);
        },
        export_as_JSON: function () {
            var json = OrderPrototype.export_as_JSON.apply(this, arguments);
            json.creation_date = this.validation_date || this.creation_date;
            json.activity_sequence = this.activity_sequence;
            return json;
        },
    });
});




