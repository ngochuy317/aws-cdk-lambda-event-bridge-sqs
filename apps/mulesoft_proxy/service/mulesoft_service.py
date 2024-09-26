import json
import urllib3

CONNECT_TIMEOUT = 2.0
READ_TIMEOUT = 7.0

class MulesoftConnectionException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class MulesoftService:
    def __init__(self, client_id, client_secret, username, password, logger):
        self.logger = logger
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret

        timeout = urllib3.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)
        self.http_pool = urllib3.PoolManager(timeout=timeout, cert_reqs='CERT_NONE', assert_hostname=False)

    def call_endpoint(self, url, method='GET', body=None, headers=None):
        auth_headers = self.build_headers()

        if headers is not None:
            auth_headers.update(headers)

        self.logger.info("Going to send %s", url)

        if method in ['PUT', 'POST', 'DELETE']:
            auth_headers['Content-Type'] = 'application/json'

            if body is not None:
                body = json.dumps(body).encode('utf-8')

        response = self.http_pool.request(
            method=method, url=url, headers=auth_headers, body=body
        )

        return self.handle_response(response, url)

    def build_headers(self):
        return urllib3.make_headers(basic_auth=f'{self.username}:{self.password}') | {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

    def handle_response(self, response, url):
        self.logger.info("Request finished with status %s and response %s", response.status, response.data)
            
        return {
            'statusCode': response.status,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': response.data if response.data else None,
            "isBase64Encoded": False
        }