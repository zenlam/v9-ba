//get the socket connection
var Socket = function () {
    this.ws = new WebSocket("wss://localhost:8686/");
    // What do we do when we get a message?
    this.handlers = {};
    var self = this;

    this.ws.onmessage = function (evt) {
        //pre-process message
        var message = JSON.parse(evt.data);
        var handler = self.handlers[message.mssg_id],
            error = message.error,
            result = message.result;

        if (handler) {
            if (error) {
                console.error("message: " + message.mssg_id + " " + error);
                handler.reject(error);
            }
            else {
                handler.resolve(result);
            }
            //remove handler from map
            delete self.handlers[message.mssg_id];
        }
    }
    // Just update our conn_status field with the connection status
    this.ws.onopen = function (evt) {
        console.log("Socket Opened");
        self.getMAC(function (resp) {
            document.cookie = 'mac_addr=' + resp;
        });
    }

    this.ws.onerror = function (evt) {
        console.error(evt);
    }

    this.ws.onclose = function (evt) {
        console.log('Socket Closed');
        //TODO: attempt to re-connect ?
        console.log('Attempt To Reconnect...')
        self.ws = new WebSocket("wss://localhost:8686/");
        setTimeout(function () {
            window.br_socket = new Socket();
        }, 1000);
    }
}

Socket.prototype._send = function (action, msg) {

    var mssg_id = action + '_' + (new Date()).getTime();
    var req = {
        action: action,
        mssg_id: mssg_id,
        params: msg
    };
    var callback = new $.Deferred();
    if (this.ws.readyState == this.ws.CLOSING || this.ws.readyState == this.ws.CLOSED || this.ws.readyState == this.ws.CONNECTING) {
        callback.reject('Socket is not opened');
        console.error('Socket not opened. Failed to send: ' + JSON.stringify(msg));
        console.log('Trying to reset websocket connection ...');
        this.ws = br_socket.ws;
        if(this.ws.readyState != this.ws.CLOSING && this.ws.readyState != this.ws.CLOSED && this.ws.readyState != this.ws.CONNECTING){
            console.log('Success !');
            this.handlers[mssg_id] = callback;
            this.ws.send(JSON.stringify(req));
        }else{
            console.log('Failed !');
        }
    }
    else {
        this.handlers[mssg_id] = callback;
        this.ws.send(JSON.stringify(req));
    }
    return callback;
}

Socket.prototype.getTerminal = function (name) {
    var self = this;

    var term = {
        name: name,
        sale: function (amount) {
            // return self._send(this.name + '_sale', {amount: amount});
            return self._send(this.name + '_sale', {amount: amount});
        },
        ewallet_sale: function(amount){
            return self._send(this.name + '_ewalletSale', {amount: amount});
        },
        bonus_point: function(amount){
            return self._send(this.name + '_bonusPoint', {amount: amount});
        },
        inquiry_qr: function(amount){
            return self._send(this.name + '_inquiryQR', {amount: amount});
        },
        redeem_point: function (amount) {
            // Convert amount to point
            var point = amount * 400;
            return self._send(this.name + '_redeemPoint', {point: point});
        },
        redeem_value: function (amount) {
            // Convert amount to point
            var value = amount;
            return self._send(this.name + '_redeemValue', {amount: value});
        }
    };

    return term;

}

Socket.prototype.getMAC = function (callback) {
    var r = this._send('MAC', null);
    r.then(callback);
    return r;
}

Socket.prototype.checkConnection = function () {
    if (this.ws.readyState == this.ws.CLOSING || this.ws.readyState == this.ws.CLOSED || this.ws.readyState == this.ws.CONNECTING) {
        var r = new $.Deferred();
        r.reject(true);
        return r;
    }
    return this._send('CHECK', null)
};

Socket.prototype.openCashDrawer = function () {
    return this._send('CASHDRAW', null);
};

Socket.prototype.POSDisplay = function (name) {
    var self = this;
    var tech = {
        name: name,

        Display: function (idAction, command, params) {
            // Parameter: idAction: '01' to swicth Mode; '02' to run Demo script; '03' to write a messenger
            // Parameter: command to display in a Mode
            // Parameter: params is integer/string or dict of  Ex: 10 or 'ABC' or {'A': 1, 'B': 'XYZ'}

            return self._send('POSDISPLAY', {
                    'idAction': idAction,
                    'command': command,
                    'params': params
                }
            )
        },

        displayProduct: function (product, quantity, unit_price, display_price) {
            var detail = quantity.toString() + 'x' + Number(unit_price).toFixed(2);
            var total = Number(display_price).toFixed(2);
            params = {'product': product, 'detail': detail, 'total': total};
            return this.Display('WRITE PRODUCT', null, params);
        },

        displayPayment: function (total, depositAmount, depositedAmount, paid, change) {
            var Fix = function (amount) {
                if (amount == 0 || amount == undefined) {
                    return null;
                }
                else {
                    return Number(amount).toFixed(2);
                }
            }
            var Total = 'Total: ' + Number(total).toFixed(2);
            var Paid = Fix(paid);
            var Change = '0.00'
            if (change != null) {
                Change = Number(change).toFixed(2);
            }
            var Deposit = null;
            if (!(depositedAmount == null || depositedAmount == 0)) {
                Deposit = Number(depositedAmount).toFixed(2);

            }
            if (!(depositAmount == null || depositAmount == 0)) {
                Deposit = Fix(depositAmount);
            }
            if (Deposit != null) {
                return this.Display('WRITE DEPOSIT', null, {
                    'total': Total,
                    'deposit': Deposit,
                    'paid': Paid,
                    'change': Change
                });
            }
            return this.Display('WRITE PAYMENT', null, {
                    'total': Total,
                    'paid': Paid,
                    'change': Change
                }
            );
        },

        displayText: function (msg) {
            var self = this
            this.Display('WRITE', 'INITIALIZE DISPLAY')
            if (msg.length > 20) {
                return self.Display('WRITE', 'WRITE UPPER SCROLL', msg);
            }
            else {
                return self.Display('WRITE', msg);
            }
        },
    }
    return tech
}


// create br_socket as a windows object
// for better encapsulation, it should 've been inside the web module
// smth link instance.web.brSocket = ...

var br_socket = new Socket();
