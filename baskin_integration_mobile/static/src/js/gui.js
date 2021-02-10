odoo.define('baskin_integration_mobile.gui', function (require) {
    "use strict";

    var PopupWidget = require('point_of_sale.popups');
    var gui = require('point_of_sale.gui');
    var core = require('web.core');
    var _t = core._t;


    gui.Gui.include({
        phone_number_input: function(buffer, input, options) {
            var pattern = buffer.match(/\((.*?)\)/);
            if (pattern) {
                var country_code = pattern[0];
            }

            var newbuf  = buffer.slice(0);

            options = options || {};

            if (input === 'CLEAR') {
                newbuf = country_code;
            } else if (input === 'BACKSPACE') {
                if (newbuf[newbuf.length - 1] != ')'){
                    newbuf = newbuf.substring(0,newbuf.length - 1);
                }
            } else if (!isNaN(parseInt(input))) {
                newbuf += input;
            }

            return newbuf;
        },
    });

});
