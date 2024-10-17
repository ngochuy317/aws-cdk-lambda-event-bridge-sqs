import json
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime


class MulesoftConnectionException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)


class MulesoftService:
    def __init__(self, client_id, client_secret, username, password, logger):
        self.logger = logger

        urllib3.disable_warnings(InsecureRequestWarning)
        timeout = urllib3.Timeout(connect=2.0, read=20.0)
        self.http_pool = urllib3.PoolManager(timeout=timeout, cert_reqs='CERT_NONE', assert_hostname=False)
        self.auth_headers = urllib3.make_headers(basic_auth=f'{username}:{password}') | {
            "client_id": client_id,
            "client_secret": client_secret,
            "Content-Type": "application/json"
        }

    def send_event_to_mule_endpoint(self, method, endpoint_url, header):
        local_header = self.auth_headers | header
        # self.logger.info("Going to send to %s with %s", endpoint_url, local_header)

        response = self.http_pool.request(
            method=method, url=endpoint_url, headers=local_header
        )

        self.logger.info("Request finished with status %s and response %s", response.status, response.data)
        if self.is_complete_failure(response.status):
            raise MulesoftConnectionException(f'Request failed with error - {response.data}')

        if response.status == 404:
            return {
                'successful_contact_counter': ""
            }

        return json.loads(response.data.decode('utf-8'))

    def get_rpc_count(self, rpc_url, acc_data):
        request_header = {
            "phone_number": acc_data["msisdn"] if len(acc_data["msisdn"]) < 11 else acc_data["msisdn"][1:],
            "branch_number": acc_data["branch_no"].zfill(5),
            "account_number": acc_data["account_id"],
            "dial_attempt_date": datetime.now().strftime('%Y-%m-%d')
        }

        response = self.send_event_to_mule_endpoint(
            method='GET', endpoint_url=rpc_url, header=request_header
        )

        return str(response['successful_contact_counter'])

    def is_complete_failure(self, status):
        return not(status == 404 or self.is_success(status))

    @staticmethod
    def is_success(status):
        return (status >= 200) & (status < 300)


