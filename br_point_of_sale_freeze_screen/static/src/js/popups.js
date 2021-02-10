odoo.define('br_point_of_sale_freeze_screen.popups', function (require) {
    "use strict";

    var gui = require('point_of_sale.gui');
    var Popups = require('point_of_sale.popups');

    var popups = null;
    for (var i=0; i<gui.Gui.prototype.popup_classes.length; i++){
        var p = gui.Gui.prototype.popup_classes[i];
        if (p.hasOwnProperty('name') && p.name === 'password'){
           popups = p;
           break;
        }
    }
    if (popups) {
        var FreezeScreenConfirmWidget = popups.widget.extend({
            click_confirm: function(){
                if( this.options.confirm ){
                    this.options.confirm.call(this,this.inputbuffer);
                }
            },
            change_cashier: function () {}
            ,
            renderElement: function(){
                var self = this;
                this._super();
                this.$el.find('.button.cancel').remove();
                this.$el.find('.title').click(function () {
                    self.options.change_cashier.call(this)
                });
            },
        });

        gui.define_popup({name:'freeze', widget: FreezeScreenConfirmWidget});
    }
});