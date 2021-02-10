from openerp.addons.base_synchro.wizard.base_synchro import RPCProxyOne, RPCProxy
from openerp import models, api, _
from openerp import pooler
from openerp.exceptions import except_orm

def _getattr(self, name):
    return lambda cr, uid, *args, **kwargs: self.rpc.execute(
        self.server.server_db,
        self.uid,
        self.server.password,
        self.ressource, name, *args)


def _get(self, ressource):
    # Cache resource to use later
    if ressource not in self.pool:
        self.pool[ressource] = RPCProxyOne(self.server, ressource)
    return self.pool[ressource]


RPCProxyOne.__getattr__ = _getattr

RPCProxy.pool = {}
RPCProxy.get = _get


class BaseSynchro(models.TransientModel):
    _inherit = 'base.synchro'
    res_cache = {}
    res_fields = {}

    @api.model
    def synchronize(self, server, object):
        pool = pooler.get_pool(self.env.cr.dbname)
        self.meta = {}
        ids = []
        pool1 = RPCProxy(server)
        pool2 = pool
        if object.action in ('d', 'b'):
            ids = pool1.get('base.synchro.obj').get_ids(
                self._cr, self.user_id,
                object.model_id.model,
                object.synchronize_date,
                eval(object.domain),
                {'action': 'd'})

        if object.action in ('u', 'b'):
            ids += pool2.get('base.synchro.obj').get_ids(
                self._cr, self.user_id.id,
                object.model_id.model,
                object.synchronize_date,
                eval(object.domain),
                {'action': 'u'})
        ids.sort()
        for dt, r, action in ids:
            id = r['id']
            if action == 'd':
                pool_src = pool1
                pool_dest = pool2
            else:
                pool_src = pool2
                pool_dest = pool1
            value = r
            if 'create_date' in value:
                del value['create_date']
            if 'write_date' in value:
                del value['write_date']
            for key, val in value.iteritems():
                if type(val) == tuple:
                    value.update({key: val[0]})
            value = self.data_transform(pool_src, pool_dest,
                                        object.model_id.model,
                                        value, action)
            id2 = self.get_id(object.id, id, action)
            if id2:
                pool_dest.get(object.model_id.model).write(self._cr,
                                                           self.user_id.id,
                                                           [id2], value)
                self.report_total += 1
                self.report_write += 1
            else:
                idnew = pool_dest.get(object.model_id.model).create(
                    self._cr,
                    self.user_id.id,
                    value)
                self.env['base.synchro.obj.line'].create({
                    'obj_id': object.id,
                    'local_id': (action == 'u') and id or idnew,
                    'remote_id': (action == 'd') and id or idnew
                })
                self.report_total += 1
                self.report_create += 1
            self.meta = {}
        return True

    @api.model
    def relation_transform(self, pool_src, pool_dest, obj_model, res_id, action):
        self.res_cache.setdefault(action, {})
        self.res_cache[action].setdefault(obj_model, {})
        if not res_id:
            return False
        elif res_id in self.res_cache[action][obj_model]:
            return self.res_cache[action][obj_model][res_id]
        self._cr.execute('''
                    select o.id from base_synchro_obj o
                    left join ir_model m on (o.model_id =m.id) where
                    m.model=%s and
                    o.active''', (obj_model,))
        obj = self._cr.fetchone()
        result = False
        if obj:
            # If the object is synchronised and found, set it
            result = self.get_id(obj[0], res_id, action)
        else:
            # If not synchronized, try to find it with name_get/name_search
            names = pool_src.get(obj_model).name_get(self._cr,
                                                     self.user_id.id,
                                                     [res_id])[0][1]
            dest = pool_dest.__dict__.get('server', '')
            dest_db = dest and dest.server_db or ''
            if not pool_dest.get(obj_model):
                war = obj_model, dest_db
                raise except_orm(_('Warning!'),
                                 _("%s object does not exist in database %s!") % (war))
            res = pool_dest.get(obj_model).name_search(self._cr,
                                                       self.user_id.id,
                                                       names, [], 'like')
            if res:
                result = res[0][0]
            else:
                # LOG this in the report, better message.
                detail = names, obj_model
                print self.report.append('WARNING: Record "%s" on relation \
                                                %s not found, set to null.' % (detail))
                result = False
        self.res_cache[action][obj_model][res_id] = result
        return result

    @api.model
    def data_transform(self, pool_src, pool_dest, obj, data, action=None):
        if action is None:
            action = {}
        self.res_fields.setdefault(action, {})
        if obj in self.res_fields[action]:
            fields = self.res_fields[action][obj]
        else:
            fields = pool_src.get(obj).fields_get(self._cr, self.user_id.id)
            self.res_fields[action][obj] = fields
        for f in fields:
            if f not in data:
                continue
            ftype = fields[f]['type']
            if ftype in ('function', 'one2many', 'one2one'):
                del data[f]
            elif ftype == 'many2one':
                if (isinstance(data[f], list)) and data[f]:
                    fdata = data[f][0]
                else:
                    fdata = data[f]
                df = self.relation_transform(pool_src, pool_dest,
                                             fields[f]['relation'],
                                             fdata, action)
                self.res_cache[action][fields[f]['relation']][fdata] = df
                data[f] = df
                if not data[f]:
                    del data[f]
            elif ftype == 'many2many':
                res = map(lambda x: self.relation_transform(
                    pool_src, pool_dest,
                    fields[f]['relation'],
                    x, action), data[f])
                data[f] = [(6, 0, [x for x in res if x])]
        del data['id']
        return data
