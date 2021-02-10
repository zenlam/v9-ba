odoo.define('br_discount.data', function (require) {

    var Model = require('web.Model');
    var data = require('web.data');

    data.DataSetStatic.include({
        init: function (parent, model, context, ids) {
            this._super(parent, model, context, ids);
            this.model = model;
            this.context = context;
            this.parent = parent;
        },
        read_slice: function (fields, options) {
            if (this.parent.name == "voucher_ids"
                && this.parent.view.model == "br.bundle.promotion"){
                this.domain = [['promotion_id', '=', this.parent_view.datarecord.id]]
                // this.context.__contexts.push("{'read_sp': 'True'}");
                this._model = new Model(this.model, this.context, this.domain);
                options = options || {};
                var self = this;
                var q = this._model.query(fields || false)
                    .filter(options.domain)
                    .context(options.context)
                    .offset(options.offset || 0)
                    .limit(options.limit || false);
                q = q.order_by.apply(q, this._sort);

                return q.all().done(function (records) {
                    q.count().done(function (count) { self._length = count; });
                    self.ids = _(records).pluck('id');
                });
            }else{
                return this._super(fields, options);
            }
        },
        size: function () {
            if (this._length !== null) {
                return this._length;
            }
            return this._super();
        }
    });
});