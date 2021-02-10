odoo.define('br_point_of_sale_track_order.log', function (require) {
    "use strict";
    var Model = require('web.Model');
    for(var storage in localStorage){
        if(storage.indexOf('POS_offline_activity') != -1){
            var data = JSON.parse(localStorage[storage]).filter(function (x) {
            return x.lines;
            });
            if(data){
                new Model('pos.track.order').call('create_from_ui', [data, storage]).done(function (result) {
                    delete localStorage[result];
                }).fail(function(error, event) {

                });
            }
        }
    }
});
