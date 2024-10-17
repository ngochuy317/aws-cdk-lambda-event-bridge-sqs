import json
import urllib3
from urllib3.exceptions import InsecureRequestWarning


class ContactProConnectionException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)


class ContactProService:
    INT_FIELDS = ["source"]

    def __init__(self, username, password, base_path, x_api_key, logger):
        self.logger = logger
        self.base_path = base_path

        urllib3.disable_warnings(InsecureRequestWarning)
        timeout = urllib3.Timeout(connect=2.0, read=20.0)
        self.http_pool = urllib3.PoolManager(timeout=timeout)
        self.auth_headers = urllib3.make_headers(basic_auth=f'{username}:{password}') | {
            "x-api-key": x_api_key,
            "Content-Type": "application/json"
        }

    def post_event_to_contact_pro(self, endpoint_path, body):
        endpoint_url = f'{self.base_path}/{endpoint_path}'
        self.logger.info("Going to send to %s with %s", endpoint_url, body)

        response = self.http_pool.request(
            method='POST', url=endpoint_url, body=json.dumps(body).encode('utf-8'), headers=self.auth_headers
        )

        self.logger.info("Request finished with status %s and response %s", response.status, response.data)
        if not self.is_success(response.status):
            raise ContactProConnectionException(f'Request failed with error - {response.data}')

        return response.data.decode('utf-8')

    def get_event_from_contact_pro(self, endpoint_path, query_fields=None):
        endpoint_url = f'{self.base_path}/{endpoint_path}'
        local_qeury_fields = self.int_query_fields(query_fields)
        self.logger.info("Going to send to %s with %s", endpoint_url, local_qeury_fields)

        response = self.http_pool.request(
            method='GET', url=endpoint_url, fields=local_qeury_fields, headers=self.auth_headers
        )

        self.logger.info("Request finished with status %s and response %s", response.status, response.data)
        if not self.is_success(response.status):
            raise ContactProConnectionException(f'Request failed with error - {response.data}')

        return json.loads(response.data.decode('utf-8'))

    def int_query_fields(self, query_fields):
        if query_fields:
            mod_fields = {}

            for k, v in query_fields.items():
                if k in self.INT_FIELDS:
                    mod_fields[k] = int(v)
                else:
                    mod_fields[k] = v

            return mod_fields

        return query_fields

    @staticmethod
    def is_success(status):
        return (status >= 200) & (status < 300)
