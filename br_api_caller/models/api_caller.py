import requests
import logging
import threading
from openerp import api, registry
import traceback
import traceback

logger = logging.getLogger(__name__)


class ApiCaller(object):
    def __init__(self, config):
        self.config = config
        self.logger = config.get_logger()
        self.session = requests.session()

    def run(self, *args, **kwargs):
        """Send all requests within configuration"""
        rqs = []
        for rq in self.config.request_ids:
            rqs.append(rq)
        if self.config.is_async:
            self._async_run(rqs, *args, **kwargs)
        else:
            self._sync_run(rqs, *args, **kwargs)

    def _async_run(self, rqs, *args, **kwargs):
        """Send requests asynchronously"""
        rq_log = []

        def _make_request(rq):
            with api.Environment.manage():
                with registry(rq.env.cr.dbname).cursor() as new_cr:
                    new_env = api.Environment(new_cr, rq.env.uid, rq.env.context)
                    rq_log.append((0, 0, self._send(rq.with_env(new_env), *args, **kwargs)))
                    new_env.cr.commit()

        threads = []
        for rq in rqs:
            t = threading.Thread(target=_make_request, args=(rq,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        self._log(rq_log)

    def _sync_run(self, rqs, *args, **kwargs):
        """Send requests synchronously"""
        rq_log = []
        for rq in rqs:
            rq_log.append((0, 0, self._send(rq, *args, **kwargs)))
        self._log(rq_log)

    def _log(self, rq_log):
        self.logger.log(rq_log)

    def _send(self, rq, *args, **kwargs):
        """Call to send request function"""
        res = {
            'request_id': rq.id,
            'status': 'success',
            'details': None
        }
        try:
            # Request data
            url = rq.url
            send_func = getattr(self, "_%s" % rq.request_method)
            headers = rq.get_request_headers()
            payload = rq.get_request_body(*args, **kwargs)

            res.update(data="======Header======\r\n %s \r\n ======Payload====== \r\n %s" % (headers, payload))
            response = send_func(url, data=None, json=payload, kwargs={'headers': headers, 'timeout': rq.timeout})
            res.update(details=response.text)
        except Exception as e:
            tb = traceback.format_exc()
            logger.info(tb)
            res.update(details=tb, status='failed')
        return res

    def _post(self, url, data=None, json=None, kwargs=None):
        """Restful: POST METHOD"""
        response = self.session.post(url, data=data, json=json, **kwargs)
        return response

    def _put(self, url, data=None, json=None, kwargs=None):
        """Restful: PUT METHOD"""
        response = self.session.put(url, data=data, json=json, **kwargs)
        return response

    def _get(self, url, data=None, json=None, kwargs=None):
        """Restful: GET METHOD"""
        response = self.session.get(url, data=data, json=json, **kwargs)
        return response

    def _delete(self, url, data=None, json=None, kwargs=None):
        """Restful: DELETE METHOD"""
        response = self.session.delete(url, data=data, json=json, **kwargs)
        return response
