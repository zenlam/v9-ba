odoo.define('baskin_integration_mobile.popups', function (require) {
    "use strict";

    var PopupWidget = require('point_of_sale.popups');
    var gui = require('point_of_sale.gui');
    var core = require('web.core');
    var _t = core._t;

    var MobilePhoneNumpadWidget = PopupWidget.extend({
        template: 'MobilePhoneNumpadWidget',
        show: function(options){
            var self = this;
            options = options || {};
            this._super(options);

            // Malaysia Tel Country Code, by default Malaysia
            var tel_code = '(60)';
            // Singapore Tel Country Code
            if (self.pos.company.id == '3') {
                tel_code = '(65)';
            }
            this.inputbuffer = tel_code + (options.value   || '');
            this.renderElement();
        },
        click_numpad: function(event){

            var newbuf = this.gui.phone_number_input(
                this.inputbuffer,
                $(event.target).data('action'));

            if (newbuf !== this.inputbuffer) {
                this.inputbuffer = ''+ newbuf;
                this.$('.value').text(this.inputbuffer);
            }
        },
        click_confirm: function(){
            this.gui.close_popup();
            if( this.options.confirm ){
                this.options.confirm.call(this,this.inputbuffer);
            }
        },
    });
    gui.define_popup({name:'mobilephone', widget:MobilePhoneNumpadWidget});
});
