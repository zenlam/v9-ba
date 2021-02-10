/**
 * Created by datnt<datnt@hanelsoft.vn> on 4/13/15.
 */

function roundAmount(amount){
    return (Math.ceil(amount*20)/20).toFixed(2);
}


function br_pos_helper ( instance, module ){
    var QWeb = instance.web.qweb,
    _t = instance.web._t;

    /**
     * Baskin Robbin Widget helper class
     */
    module.BrWidgetHelper = module.PosBaseWidget.extend({
        init:function(parent,options){
            this._super(parent, options);
            this.elNode = parent.el;
        },
        set_mode_back_to_payment: function() {
    		this.numpad_state.set({mode: 'payment'});
            this.numpad_state = this.pos_widget.numpad.state;
    	},
        set_value: function(val) {
            var selected_line =this.pos.get('selectedOrder').selected_paymentline;
            if(selected_line){
                selected_line.set_amount(val);
                selected_line.node.querySelector('input').value = selected_line.amount.toFixed(2);
            }
        },
        enable_numpad: function(){
            this.disable_numpad();  //ensure we don't register the callbacks twice
            if(this.numpad_state){
                this.numpad_state.reset();
                this.numpad_state.changeMode('payment');
                this.numpad_state.bind('set_value',   this.set_value, this);
                this.numpad_state.bind('change:mode', this.set_mode_back_to_payment, this);
            }

        },
        disable_numpad: function(){
            if(this.numpad_state){
                this.numpad_state.unbind('set_value',  this.set_value);
                this.numpad_state.unbind('change:mode',this.set_mode_back_to_payment);
            }
        },
        get_object_size: function (obj) {
            var size = 0, key;
            for (key in obj) {
                if (obj.hasOwnProperty(key)) size++;
            }
            return size;
        },
        get_random_number: function () {
            var random =Math.floor(Math.random()*90000) + 10000;
            return random
        },
        /**
         * Overwrites obj1's values with obj2's and adds obj2's if non existent in obj1
         * @param obj1
         * @param obj2
         * @returns obj3 a new object based on obj1 and obj2
         */
        merge_options: function (obj1, obj2) {
            var obj3 = {};
            for (var attrname in obj1) {
                obj3[attrname] = obj1[attrname];
            }
            for (var attrname in obj2) {
                obj3[attrname] = obj2[attrname];
            }
            return obj3;
        },

        is_even: function (n) {
            function isNumber(n)
            {
               return n == parseFloat(n);
            }
            return isNumber(n) && (n % 2 == 0);
        },

        removeCurrentMode: function () {
            var buttons = document.querySelector('.current-mode');
            if ( buttons ){
                buttons.className = buttons.className.replace('current-mode','');
            }
        },


        alert:function(str){
	         var self = this;
	         return my_pos_widget.screen_selector.show_popup('br-error',{message:_t(str)});
        },

        /* End Check MayBank Discount */
        reset_discount:function(type){
            var order = this.pos.get_order();
            if (type === 'discount_staff'){
                order.setDiscountStaff(null);
            }
            if (type === 'discount_mb'){
                //order.discount_MB = 0;
                order.setDiscountMaybank(null);
            }
        },
        truncate_string: function(str){
        
            if (!str)
                return '';
            var len = 50;
            if (str.length >  len) {
                // trims it to 17 charcters
                return (str.substr(0,len - 3) + '...');
            }
            return str;
        },
    });
}