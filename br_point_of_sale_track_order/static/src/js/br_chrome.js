odoo.define('br_point_of_sale_track_order.br_chrome', function(require){
    var chrome = require('point_of_sale.chrome');
    var core = require('web.core');
    var _t = core._t;
    var OrderSelectorWidget = chrome.OrderSelectorWidget;
    OrderSelectorWidget.include({
        deleteorder_click_handler: function(event, $el) {
            var self  = this;
            var order = this.pos.get_order();
            if (!order) {
                return;
            } else if ( !order.is_empty() ){
                this.gui.show_popup('br_delete_confirm',{
                    'title': _t('Destroy Current Order ?'),
                    'body': _t('You will lose any data associated with the current order, please fill in remark: '),
                    confirm: function(remark){
                        self.pos.delete_current_order({'remark': remark});
                    },
                });
            } else {
                this.pos.delete_current_order();
            }
        },
    });
});
