import json
import os
from datetime import datetime
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from sinch_proxy.const import ENV_LAMBDA_REQUEST_LOG_TABLE
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ[ENV_LAMBDA_REQUEST_LOG_TABLE] = 'test-table'

from sinch_proxy import main



PROCESSING_TTL = 5 * 60  # 5 minutes
EVENT_TTL = 30 * 24 * 60 * 60  # 30 days


class TestSinchProxyHandler1:
    # Existing tests in TestSinchProxyHandler

    @patch('sinch_proxy.main.request_log')
    def test_get_processed_event_none_if_event_not_exist(self, mock_request_log):
        test_event = {
            'unique_request_id': "test1"
        }

        assert main.get_processed_event(test_event) is None

    @patch('sinch_proxy.main.request_log')
    def test_get_processed_event_none_if_event_expired(self, mock_request_log):
        mock_request_log.get_item.return_value = {
            'Item': {
                'expire_ts': int(datetime.now().timestamp()) - 100
            }
        }
        test_event = {
            'unique_request_id': "test1"
        }

        assert main.get_processed_event(test_event) is None

    @patch('sinch_proxy.main.request_log')
    def test_get_processed_event_not_none_if_event_exist(self, mock_request_log):
        mock_request_log.get_item.return_value = {
            'Item': {
                'unique_request_id': "test1",
                'expire_ts': int(datetime.now().timestamp()) + 100
            }
        }
        test_event = {
            'unique_request_id': "test1"
        }

        assert main.get_processed_event(test_event) is not None

    @patch('sinch_proxy.main.datetime')
    @patch('sinch_proxy.main.request_log')
    def test_log_processing_event(self, mock_request_log, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0)

        test_event = {
            'unique_request_id': "test1"
        }

        main.log_processing_event(test_event)
        mock_request_log.put_item.assert_called_once_with(
            Item={
                'unique_request_id': 'test1',
                'acs_data': {'unique_request_id': 'test1'},
                'event_status': 'MA_PROCESSING',
                'expire_ts': str(int(datetime(2024, 1, 1, 12, 0, 0).timestamp()) + PROCESSING_TTL)
            }
        )

    @patch('sinch_proxy.main.datetime')
    @patch('sinch_proxy.main.request_log')
    def test_log_processed_event(self, mock_request_log, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0)
        test_event = {
            'unique_request_id': "test1"
        }
        test_response = {
            'message_id': 'message_id1',
            'accepted_time': '2024-01-01T00:00:00Z'
        }

        main.log_processed_event(test_event, test_response)
        mock_request_log.put_item.assert_called_once_with(
            Item={
                'SINCH_ACCEPTED': {
                    'message_id': 'message_id1',
                    'accepted_time': '2024-01-01T00:00:00Z'
                },
                'unique_request_id': 'test1',
                'message_id': 'message_id1',
                'event_status': 'SINCH_ACCEPTED',
                'last_update_ts': '2024-01-01T00:00:00Z',
                'expire_ts': str(int(datetime(2024, 1, 1, 12, 0, 0).timestamp()) + EVENT_TTL)
            }
        )
    
    # Additional Tests for Coverage
    def test_lambda_handler_no_records(self):
        # Updated event structure to have "Records" as an empty list
        event = {"Records": []}
        context = {}
        response = main.lambda_handler(event, context)
        
        # Assertions to check the response is still as expected
        assert response['statusCode'] == 200
        assert response['body'] == json.dumps('OK')
        assert 'batchItemFailures' in response
        assert len(response['batchItemFailures']) == 0


    def test_lambda_handler_invalid_event_body(self):
        event = {"Records": [{"body": "invalid-json", "messageId": "msg1"}]}
        context = {}
        response = main.lambda_handler(event, context)
        assert response['statusCode'] == 200
        assert response['batchItemFailures'][0]['itemIdentifier'] == "msg1"

    @patch('sinch_proxy.main.request_log')
    def test_process_event_missing_mandatory_parameter(self, mock_request_log):
        test_event = {
            'unique_request_id': "test1",
            'phone_number': '+1234567890',
            'message_body': 'Hello'
        }  # Missing 'short_code'
        with pytest.raises(ValueError, match="Missing mandatory parameter: 'short_code'. Current value: None"):
            main.process_event(test_event)

    @patch('sinch_proxy.main.request_log')
    def test_log_processing_event_client_error(self, mock_request_log):
        mock_request_log.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': '400', 'Message': 'Bad Request'}},
            operation_name='PutItem'
        )
        test_event = {'unique_request_id': "test1"}
        with pytest.raises(ClientError):
            main.log_processing_event(test_event)

    @patch('sinch_proxy.main.request_log')
    def test_log_processed_event_unexpected_error(self, mock_request_log):
        mock_request_log.put_item.side_effect = Exception("Unexpected error")
        db_event = {'unique_request_id': '12345'}
        sinch_response = {'message_id': 'msg123', 'accepted_time': '2024-09-13T12:00:00Z'}
        with pytest.raises(Exception):
            main.log_processed_event(db_event, sinch_response)

    @patch('sinch_proxy.main.request_log')
    def test_get_processed_event_client_error(self, mock_request_log):
        mock_request_log.get_item.side_effect = ClientError(
            error_response={'Error': {'Code': '400', 'Message': 'Bad Request'}},
            operation_name='GetItem'
        )
        test_event = {'unique_request_id': "test1"}
        with pytest.raises(ClientError):
            main.get_processed_event(test_event)

    def test_parse_event_body_empty_string(self):
        result = main.parse_event_body("")
        assert result == {}

    def test_parse_event_body_invalid_json(self):
        result = main.parse_event_body("invalid-json")
        assert result == {}

    def test_parse_event_body_valid_json(self):
        body = '{"data": [{"key": "value"}]}'
        result = main.parse_event_body(body)
        assert result['data'][0]['key'] == "value"

    def test_parse_event_body_none_input(self):
        result = main.parse_event_body(None)
        assert result == {}