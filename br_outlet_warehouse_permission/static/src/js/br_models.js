odoo.define('br_outlet_warehouse_permission.models', function (require) {
    "use strict";

    var models = require('point_of_sale.models');
    var utils = require('web.utils');
    var parentPrototype = models.PosModel.prototype;
    var parentOrderlinePrototype = models.Orderline.prototype;
    var round_pr = utils.round_precision;
    var OrderPrototype = models.Order.prototype;
    var Model = require('web.DataModel');
    var screens = require('point_of_sale.screens');
    models.Order.prototype.UNLIMITED = 9999;

    models.PosModel = models.PosModel.extend({
        /* Override initialize function */
        initialize: function (session, attribute) {
            parentPrototype.initialize.call(this, session, attribute);
            var self = this,
                original_models = self.models,
                new_models = original_models;
            new_models.push(
                {
                    model: 'res.users',
                    fields: ['name', 'pos_security_pin', 'groups_id', 'barcode', 'outlet_ids'],
                    loaded: function (self, users) {
                        // we attribute a role to the user, 'cashier' or 'manager', depending
                        // on the group the user belongs.
                        var pos_users = [];
                        for (var i = 0; i < users.length; i++) {
                            var user = users[i];
                            for (var j = 0; j < user.groups_id.length; j++) {
                                var group_id = user.groups_id[j];
                                if (group_id === self.config.group_pos_manager_id[0]) {
                                    user.role = 'manager';
                                    break;
                                } else if (group_id === self.config.group_pos_user_id[0]) {
                                    user.role = 'cashier';
                                }
                            }
                            var belong_outlet = false;
                            if (user.outlet_ids) {
                                for (var k = 0; k < user.outlet_ids.length; k++) {
                                    var outlet_id = user.outlet_ids[k];
                                    if (outlet_id === self.config.outlet_id[0]) {
                                        belong_outlet = true;
                                        break;
                                    }
                                }
                            }

                            if (user.role && belong_outlet) {
                                pos_users.push(user);
                            }
                            // replace the current user with its updated version
                            if (user.id === self.user.id) {
                                self.user = user;
                            }
                        }
                        self.users = pos_users;
                    }
                }
            );
            self.models = new_models;
        }
    });
});
