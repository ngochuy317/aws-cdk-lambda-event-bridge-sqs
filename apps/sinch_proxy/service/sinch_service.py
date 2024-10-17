import json
import os  # Import to read environment variables
import urllib3
from datetime import datetime, timedelta

class SinchConnectionException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)

class SinchService:
    SINCH_CONV_API = 'https://us.conversation.api.sinch.com/v1/projects'

    def __init__(self, logger, ssm_service, client_credential_path, refresh_interval_minutes=15):
        self.logger = logger
        self.ssm_service = ssm_service
        self.cached_parameters = {}
        self.client_credential_path = client_credential_path
        self.last_cache_update_time = datetime.min  # Initialize with the earliest possible date
        self.refresh_interval_minutes = refresh_interval_minutes

        timeout = urllib3.Timeout(connect=2.0, read=20.0)
        self.http_pool = urllib3.PoolManager(timeout=timeout)

        # Fetch initial parameters
        self._safe_fetch_parameters()

    def _safe_fetch_parameters(self):
        """Safely fetches parameters and handles exceptions."""
        try:
            self.fetch_parameters()
        except Exception as e:
            self.logger.exception(f"Error fetching parameters: {e}")

    def fetch_parameters(self):
        """Fetches parameters from the SSM parameter store and updates the cache."""
        required_fields = {"token", "app_id", "project_id", "client_id", "client_secret"}
        self.cached_parameters = {}
        
        parameters = self.ssm_service.get_parameters_by_path(self.client_credential_path)
        if not parameters:
            raise ValueError("No parameters found in SSM parameter store.")
        
        for param in parameters:
            try:
                param_name = param['Name'].rsplit('/', 1)[-1]
                param_value = param['Value']
                parsed_value = json.loads(param_value)

                # Validate that all required fields are present and are not empty
                if not isinstance(parsed_value, dict):
                    self.logger.error(f"Parameter {param_name} is not a valid JSON string, please update SSM parameter value.")
                    continue  # Skip invalid parameters

                missing_fields = required_fields - parsed_value.keys()
                if missing_fields:
                    self.logger.error(f"Missing required fields {missing_fields} in parameter {param_name}, skipping.")
                    continue  # Skip if required fields are missing

                # Ensure all fields have valid non-empty values
                for field in required_fields:
                    if not parsed_value[field]:
                        self.logger.error(f"Field {field} in parameter {param_name} is empty or invalid, skipping.")
                        continue  # Skip if any required field is empty or invalid

                # Cache the valid parameters
                self.cached_parameters[param_name] = parsed_value
                self.logger.debug(f"Successfully cached {param_name} with value {parsed_value}")

            except json.JSONDecodeError:
                self.logger.exception(f"Error parsing parameter {param_name} with value {param_value}")
            except Exception as e:
                self.logger.exception(f"Error fetching parameter {param_name}: {e}")

        # Update the last cache update time
        self.last_cache_update_time = datetime.now()

    def _update_cache_if_needed(self):
        """Checks if the cache needs to be updated and updates it if necessary."""
        if datetime.now() - self.last_cache_update_time > timedelta(minutes=self.refresh_interval_minutes):
            self.logger.info(f"Updating cached parameters after {self.refresh_interval_minutes} minutes.")
            self._safe_fetch_parameters()

    def get_auth_headers(self, token):
        """Returns the authorization headers for a given token."""
        if not token:
            raise ValueError("Authorization token is required but missing.")
        return {
            "Authorization": f"Bearer {token}"
        }

    def post_event_to_sinch(self, event, method, url_path, token, sms_code=None):
        """Posts an event to the Sinch API."""
        if not sms_code or sms_code not in self.cached_parameters:
            raise ValueError(f"Invalid or missing 'sms_code': {sms_code}")

        payload = json.dumps(event).encode('utf-8')
        endpoint_url = f"{self.SINCH_CONV_API}/{self.cached_parameters[sms_code]['project_id']}/{url_path}"

        self.logger.info(f"Calling {endpoint_url} with {payload}")

        response = self._send_request(method, endpoint_url, token, payload)

        # Handle token refresh if authentication failed or response is None
        if not response or (self.is_auth_failed(response.status) and sms_code):
            self.logger.warning(f"Token for {sms_code} has expired or request failed, refreshing token")
            self._safe_fetch_parameters()
            token = self.cached_parameters[sms_code].get('token')
            if not token:
                raise SinchConnectionException(f"Failed to refresh token for {sms_code}")
            
            # Retry the request with the refreshed token
            response = self._send_request(method, endpoint_url, token, payload)

            if self.is_auth_failed(response.status):
                self.logger.error(f"Token for {sms_code} has expired or request failed.")

        # If response is still not successful, handle it
        if not response or not self.is_success(response.status):
            self.logger.error(
                f"Request to {endpoint_url} failed with status {response.status if response else 'Unknown'} "
                f"and data {response.data if response else 'No Data'}"
            )
            raise SinchConnectionException(
                f"Request failed with error - {response.data if response else 'No response received'}"
            )

        # Attempt to parse the response JSON
        return self._parse_response(response)

    def _send_request(self, method, url, token, payload):
        """Sends a request to the specified URL with the provided method, token, and payload."""
        try:
            return self.http_pool.request(
                method=method, url=url, headers=self.get_auth_headers(token), body=payload
            )
        except Exception as e:
            self.logger.exception(f"Request failed with error: {e}")
            return None

    def _parse_response(self, response):
        """Parses the response JSON and handles errors."""
        try:
            return json.loads(response.data.decode('utf-8'))
        except json.JSONDecodeError as e:
            self.logger.exception(f"Failed to parse response JSON: {e}")
            raise SinchConnectionException(f"Invalid JSON response: {e}")

    def post_message(self, conversation_metadata, unique_request_id, phone_number, sms_code, message_body):
        """Posts a message to the Sinch API."""
        if not sms_code:
            raise ValueError("sms_code is required.")

        # Ensure the cached parameters are up to date
        self._update_cache_if_needed()

        param_data = self.cached_parameters.get(sms_code)
        if not param_data:
            self.logger.error(f"SSM parameter for for sms_code: {sms_code} does not exist")
            raise ValueError(f"No data found for sms_code: {sms_code}")

        self.logger.debug(f"Found data for sms_code: {sms_code}")
        self.logger.debug(f"Data: {param_data}")

        message = {
            "app_id": param_data['app_id'],
            "message_metadata": json.dumps({"unique_request_id": unique_request_id}),
            "callback_url": self.ssm_service.get_ssm_parameter_with_env('MA_MESSAGE_DELIVERY_CALLBACK_URL'),
            "conversation_metadata": conversation_metadata,
            "recipient": {
                "identified_by": {
                    "channel_identities": [
                        {
                            "channel": "SMS",
                            "identity": phone_number
                        }
                    ]
                }
            },
            "message": {
                "text_message": {
                    "text": message_body
                }
            },
            "ttl": "1800s",
            "correlation_id": unique_request_id,
            "channel_priority_order": [
                "SMS"
            ],
            "channel_properties": {
                "SMS_SENDER": sms_code
            }
        }

        return self.post_event_to_sinch(message, 'POST', 'messages:send', token=param_data['token'], sms_code=sms_code)

    @staticmethod
    def is_success(status):
        """Checks if the response status is a success (200-299)."""
        return 200 <= status < 300

    @staticmethod
    def is_auth_failed(status):
        """Checks if the response status indicates authentication failure (401)."""
        return status == 401