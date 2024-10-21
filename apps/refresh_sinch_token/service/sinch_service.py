import json
import urllib3


class SinchConnectionException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)


class SinchTokenService:
    GRANT_TYPE_BODY = {
        'grant_type': 'client_credentials'
    }

    def __init__(self, client_id, client_secret, auth_url, logger):
        self.auth_url = auth_url
        self.logger = logger

        timeout = urllib3.Timeout(connect=2.0, read=20.0)
        self.http_pool = urllib3.PoolManager(timeout=timeout)
        self.auth_headers = urllib3.make_headers(basic_auth=f'{client_id}:{client_secret}')

    def generate_token(self):
        payload = json.dumps(self.GRANT_TYPE_BODY).encode('utf-8')

        self.logger.debug(f"Sending {payload} and {self.auth_headers} to {self.auth_url}")
        response = self.http_pool.request(
            method='POST', url=self.auth_url, headers=self.auth_headers, fields=self.GRANT_TYPE_BODY
        )

        self.logger.info("Request finished with status %s and response %s", response.status, response.data)
        if not self.is_success(response.status):
            raise SinchConnectionException(f'Request failed with error - {response.data}')

        return json.loads(response.data.decode('utf-8'))["access_token"]

    @staticmethod
    def is_success(status):
        return (status >= 200) & (status < 300)