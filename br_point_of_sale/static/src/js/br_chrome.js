odoo.define('br_point_of_sale.chrome', function (require) {
    'use strict'

    var chrome = require('point_of_sale.chrome');

    chrome.Chrome.include({
        init: function () {
            this._super();
            this.posDisplay = window.br_socket.POSDisplay('POS Widget');
        },

        icecream_quotes: [
            'You can\'t buy happiness but you can buy ice-cream.\nThat\'s kinda the same thing',
            'Life is like an ice-cream.\nTaste it before it melts',
            'It\'s never too cold for ice-cream',
            'My head says go to the gym.\nMy heart says eat more ice-cream',
            'All you need is love and lots of ice-cream'
        ],

        baskin_progress: function (progress) {
            this.$('.loading-baskin').removeClass('oe_hidden');
            this.$('.loading-baskin .loading-progress').css({'height': '' + (100 - Math.floor(progress * 100)) + '%'});
            if (this.quoteTimer === undefined) {
                this.quoteTimer = this.displayQuote();
            }
        },

        displayQuote: function () {
            var $msg = this.$('.baskin_message');
            if ($msg && this.quoteTimer) {
                if (!$msg.text()) {
                    var idx = Math.floor(Math.random() * this.icecream_quotes.length);
                    $msg.text(this.icecream_quotes[idx]);
                }
            } else {
                var self = this;
                return setTimeout(function () {
                    self.quoteTimer = self.displayQuote();
                }, 1200);
            }
        },

        done_baskin_progress: function () {
            this.$('.loading-baskin').addClass('oe_hidden');
            if (this.quoteTimer)
                clearTimeout(this.quoteTimer);
                this.posDisplay.displayText(this.getIdleMsg());
        },

        loading_message: function (msg, progress) {
            this._super(msg, progress);
            if (this.loading_server_data) {
                // show the baskin loader image
                this.baskin_progress(progress);
            }
        },
        getIdleMsg: function () {
            //Idle Message is not coded yet
            // var msg = module.POS_CONFIG_SETTINGS.idle_time;
            // if (!msg) {
            var msg = 'Welcome to Baskin-Robbin!';
            // }
            return msg;
        },
    });
});