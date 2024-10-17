import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from sinch_proxy.service.sinch_service import SinchService, SinchConnectionException  # Assume the class is in sinch_service.py

class TestSinchService:
    def setup_method(self):
        """Setup mock objects and environment variables before each test."""
        self.logger = MagicMock()
        self.ssm_service_mock = MagicMock()
        self.client_credential_path = '/dummy/path'
        self.token = 'mock-token'

    def test_initialization_with_default_value(self):
        """Test initialization when no environment variable or parameter is provided for refresh interval."""
        sinch_service = SinchService(
            logger=self.logger,
            ssm_service=self.ssm_service_mock,
            client_credential_path=self.client_credential_path
        )
        assert sinch_service.refresh_interval_minutes is 15

    def test_initialization_with_provided_value(self):
        """Test initialization when refresh interval is explicitly provided."""
        sinch_service = SinchService(
            logger=self.logger,
            ssm_service=self.ssm_service_mock,
            client_credential_path=self.client_credential_path,
            refresh_interval_minutes=5
        )
        assert sinch_service.refresh_interval_minutes == 5

    def test_fetch_parameters_success(self):
        """Test that parameters are fetched and cached correctly from SSM."""
        # Mock return value from SSM with all required fields
        self.ssm_service_mock.get_parameters_by_path.return_value = [
            {
                'Name': '/dummy/path/param1',
                'Value': json.dumps({
                    'token': 'mock-token',
                    'app_id': 'mock-app-id',
                    'project_id': 'mock-project-id',
                    'client_id': 'mock-client-id',
                    'client_secret': 'mock-client-secret'
                })
            }
        ]

        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=5)
        sinch_service.fetch_parameters()

        # Assert that the parameter is cached correctly
        assert 'param1' in sinch_service.cached_parameters
        cached_param = sinch_service.cached_parameters['param1']
        assert cached_param['token'] == 'mock-token'
        assert cached_param['app_id'] == 'mock-app-id'
        assert cached_param['project_id'] == 'mock-project-id'
        assert cached_param['client_id'] == 'mock-client-id'
        assert cached_param['client_secret'] == 'mock-client-secret'

    def test_fetch_parameters_missing_fields(self):
        """Test that parameters are skipped when required fields are missing."""
        # Mock return value with missing 'app_id' and 'client_secret'
        self.ssm_service_mock.get_parameters_by_path.return_value = [
            {
                'Name': '/dummy/path/param1',
                'Value': json.dumps({
                    'token': 'mock-token',
                    'project_id': 'mock-project-id',
                    'client_id': 'mock-client-id',
                    # Missing 'app_id' and 'client_secret'
                })
            }
        ]

        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=5)
        sinch_service.fetch_parameters()

        # Assert that the parameter is not cached due to missing fields
        assert 'param1' not in sinch_service.cached_parameters

    def test_fetch_parameters_no_parameters(self):
        """Test that fetch_parameters raises an error when no parameters are found."""
        self.ssm_service_mock.get_parameters_by_path.return_value = []
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=5)

        with pytest.raises(ValueError, match="No parameters found in SSM parameter store."):
            sinch_service.fetch_parameters()

    def test_fetch_parameters_invalid_json(self):
        """Test that fetch_parameters logs an exception for invalid JSON."""
        self.ssm_service_mock.get_parameters_by_path.return_value = [
            {'Name': '/dummy/path/param1', 'Value': '{invalid-json}'}
        ]
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=5)
        sinch_service.fetch_parameters()

        self.logger.exception.assert_called_with("Error parsing parameter param1 with value {invalid-json}")

    def test_update_cache_if_needed_refreshes_cache(self):
        """Test that _update_cache_if_needed correctly refreshes the cache if needed."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)
        sinch_service.last_cache_update_time = datetime.now() - timedelta(minutes=11)  # 1 minute past interval

        with patch.object(sinch_service, '_safe_fetch_parameters') as mock_fetch:
            sinch_service._update_cache_if_needed()
            mock_fetch.assert_called_once()

    def test_update_cache_if_needed_does_not_refresh_cache(self):
        """Test that _update_cache_if_needed does not refresh the cache when not needed."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)
        sinch_service.last_cache_update_time = datetime.now()  # Cache is up-to-date

        with patch.object(sinch_service, '_safe_fetch_parameters') as mock_fetch:
            sinch_service._update_cache_if_needed()
            mock_fetch.assert_not_called()

    def test_post_event_to_sinch_success(self):
        """Test that post_event_to_sinch sends a request and returns the correct response."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)
        sinch_service.cached_parameters['param1'] = {'token': 'mock-token', 'project_id': 'mock-project-id'}

        with patch.object(sinch_service, '_send_request', return_value=MagicMock(status=200, data=json.dumps({'message': 'Success'}).encode('utf-8'))):
            response = sinch_service.post_event_to_sinch({'test': 'test'}, 'POST', 'api/test', self.token, 'param1')
            assert response['message'] == 'Success'

    def test_post_event_to_sinch_auth_failure_and_retry(self):
        """Test that post_event_to_sinch retries on authentication failure."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)
        
        # Mock initial cached parameter
        sinch_service.cached_parameters['param1'] = {
            'token': 'mock-token', 
            'project_id': 'mock-project-id',
            'app_id': 'mock-app-id',
            'client_id': 'mock-client-id',
            'client_secret': 'mock-client-secret'
        }

        # Mock the refresh of parameters to include updated token
        self.ssm_service_mock.get_parameters_by_path.return_value = [
            {
                'Name': '/dummy/path/param1',
                'Value': json.dumps({
                    'token': 'refreshed-token',
                    'app_id': 'mock-app-id',
                    'project_id': 'mock-project-id',
                    'client_id': 'mock-client-id',
                    'client_secret': 'mock-client-secret'
                })
            }
        ]

        # Mock the _send_request method to simulate auth failure followed by success
        with patch.object(sinch_service, '_send_request', side_effect=[
            MagicMock(status=401),  # First request fails with auth error
            MagicMock(status=200, data=json.dumps({'message': 'Success'}).encode('utf-8'))  # Second request succeeds
        ]):
            response = sinch_service.post_event_to_sinch({'test': 'test'}, 'POST', 'api/test', self.token, 'param1')

        # Assert the token was refreshed and the second request succeeded
        assert response['message'] == 'Success'

    def test_post_event_to_sinch_failure_after_retry(self):
        """Test that post_event_to_sinch raises an exception if both attempts fail."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)
        
        # Mock initial cached parameter
        sinch_service.cached_parameters['param1'] = {
            'token': 'mock-token', 
            'project_id': 'mock-project-id',
            'app_id': 'mock-app-id',
            'client_id': 'mock-client-id',
            'client_secret': 'mock-client-secret'
        }

        # Mock the refresh of parameters to include updated token
        self.ssm_service_mock.get_parameters_by_path.return_value = [
            {
                'Name': '/dummy/path/param1',
                'Value': json.dumps({
                    'token': 'refreshed-token',
                    'app_id': 'mock-app-id',
                    'project_id': 'mock-project-id',
                    'client_id': 'mock-client-id',
                    'client_secret': 'mock-client-secret'
                })
            }
        ]

        # Mock the _send_request method to simulate auth failure followed by another failure
        with patch.object(sinch_service, '_send_request', side_effect=[
            MagicMock(status=401),  # First request fails with auth error
            MagicMock(status=500)   # Second request fails again
        ]):
            with pytest.raises(SinchConnectionException, match="Request failed with error - .*"):
                sinch_service.post_event_to_sinch({'test': 'test'}, 'POST', 'api/test', self.token, 'param1')

    def test_post_event_to_sinch_parsing_error(self):
        """Test that post_event_to_sinch raises an exception on JSON parsing error."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)
        sinch_service.cached_parameters['param1'] = {'token': 'mock-token', 'project_id': 'mock-project-id'}

        with patch.object(sinch_service, '_send_request', return_value=MagicMock(status=200, data=b'not-a-json')):
            with pytest.raises(SinchConnectionException, match="Invalid JSON response: .*"):
                sinch_service.post_event_to_sinch({'test': 'test'}, 'POST', 'api/test', self.token, 'param1')

    def test_post_message_with_missing_sms_code(self):
        """Test that post_message raises an error when sms_code is missing."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)

        with pytest.raises(ValueError, match="sms_code is required."):
            sinch_service.post_message({}, 'unique_id', '1234567890', None, 'Hello')

    def test_post_message_with_invalid_sms_code(self):
        """Test that post_message raises an error when sms_code is not found in cache."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)

        with pytest.raises(ValueError, match="No data found for sms_code: invalid_code"):
            sinch_service.post_message({}, 'unique_id', '1234567890', 'invalid_code', 'Hello')

    def test_send_request_network_failure(self):
        """Test that _send_request logs an exception on network failure."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)

        with patch('urllib3.PoolManager.request', side_effect=Exception("Network failure")):
            sinch_service._send_request('POST', 'url', 'token', b'{}')
            self.logger.exception.assert_called_with("Request failed with error: Network failure")

    def test_parse_response_invalid_json(self):
        """Test that _parse_response raises an exception on invalid JSON response."""
        sinch_service = SinchService(self.logger, self.ssm_service_mock, self.client_credential_path, refresh_interval_minutes=10)
        mock_response = MagicMock()
        mock_response.data = b'invalid-json'

        with pytest.raises(SinchConnectionException, match="Invalid JSON response: .*"):
            sinch_service._parse_response(mock_response)