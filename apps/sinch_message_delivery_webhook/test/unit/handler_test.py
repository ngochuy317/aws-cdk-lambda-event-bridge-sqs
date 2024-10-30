import pytest, os, json, sys
from unittest.mock import patch

# Set the environment variables required by main.py
os.environ['REQUEST_LOG_TABLE'] = 'dummy_value'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['SMS_EVENT_BUS'] = 'SMS_EVENT_BUS'

from sinch_message_delivery_webhook.main import (
    check_bot_entries,
    prepare_db_event,
    get_logged_event,
    lambda_handler,
    post_event,
)


class TestSinchMessageDeliveryWebhookHandler:

    def setup_method(self):
        self.sinch_event_record = {
            "Records": [{
                "body": json.dumps({
                    "correlation_id": "12345",
                    "event_time": "2023-10-01T00:00:00Z",
                    "message_delivery_report": {
                        "status": "DELIVERED"
                    }
                })
            }]
        }
    
    def create_sample_db_event(self, last_update_ts, status):
        return {
            'unique_request_id': '12345',
            'last_update_ts': last_update_ts,
            status: {
                'event_time': '2023-09-30T00:00:00Z'
            }
        }

    def test_check_bot_entries_positive(self):
        event = {
            'message_delivery_report': {
                'metadata': json.dumps({
                    'chl_bot_id': 'US-lsasli81',
                    'chl_bot_version': 'DRAFT'
                })
            }
        }
        assert check_bot_entries(event) == True

    def test_check_bot_entries_negative_no_metadata(self):
        event = {
            'message_delivery_report': {}
        }
        assert check_bot_entries(event) == False

    def test_check_bot_entries_negative_no_bot_id(self):
        event = {
            'message_delivery_report': {
                'metadata': json.dumps({
                    'chl_bot_version': 'DRAFT'
                })
            }
        }
        assert check_bot_entries(event) == False

    def test_check_bot_entries_negative_no_bot_version(self):
        event = {
            'message_delivery_report': {
                'metadata': json.dumps({
                    'chl_bot_id': 'US-lsasli81'
                })
            }
        }
        assert check_bot_entries(event) == False

    def test_prepare_db_event_update_event(self):
        db_event = self.create_sample_db_event('2023-09-29T00:00:00Z', 'DELIVERED')
        sinch_response = {
            "correlation_id": "12345",
            "event_time": "2023-10-01T00:00:00Z",
            "message_delivery_report": {"status": "DELIVERED"}
        }
        result = prepare_db_event(db_event, sinch_response)
        assert result is not None
        assert result['last_update_ts'] == "2023-10-01T00:00:00Z"
        assert result['event_status'] == "DELIVERED"

    def test_prepare_db_event_outdated_event(self):
        db_event = self.create_sample_db_event('2023-10-02T00:00:00Z', 'DELIVERED')
        sinch_response = {
            "correlation_id": "12345",
            "event_time": "2023-08-01T00:00:00Z",
            "message_delivery_report": {"status": "DELIVERED"}
        }
        result = prepare_db_event(db_event, sinch_response)
        assert result is None

    @patch('sinch_message_delivery_webhook.main.request_log')
    def test_get_logged_event(self, mock_request_log):
        mock_request_log.get_item.return_value = {'Item': {'unique_request_id': '12345'}}
        result = get_logged_event({"correlation_id": "12345"})
        assert result == {'unique_request_id': '12345'}

    @patch('sinch_message_delivery_webhook.main.request_log')
    def test_get_logged_event_no_item(self, mock_request_log):
        mock_request_log.get_item.return_value = {}
        result = get_logged_event({"correlation_id": "12345"})
        assert result is None

    @patch('sinch_message_delivery_webhook.main.event_bridge_client')
    def test_post_event(self, mock_event_bridge_client):
        mock_event_bridge_client.put_events.return_value = {'FailedEntryCount': 0}
        post_event({"example": "data"})
        mock_event_bridge_client.put_events.assert_called_once()

    @patch('sinch_message_delivery_webhook.main.get_logged_event')
    @patch('sinch_message_delivery_webhook.main.prepare_db_event')
    @patch('sinch_message_delivery_webhook.main.post_event')
    @patch('sinch_message_delivery_webhook.main.request_log')
    def test_lambda_handler_success(self, mock_request_log, mock_post_event, mock_prepare_db_event, mock_get_logged_event):
        mock_get_logged_event.return_value = {'unique_request_id': '12345'}
        mock_prepare_db_event.return_value = {'prepared_event': True}
        mock_request_log.put_item.return_value = {}

        result = lambda_handler(self.sinch_event_record, None)
        
        mock_request_log.put_item.assert_called_once()
        mock_post_event.assert_called()
        assert result['statusCode'] == 200

    @patch('sinch_message_delivery_webhook.main.logger')
    @patch('sinch_message_delivery_webhook.main.get_logged_event')
    @patch('boto3.resource')
    def test_lambda_handler_no_logged_event(self, mock_dynamodb, mock_get_logged_event, mock_logger):
        mock_get_logged_event.return_value = None

        lambda_handler(self.sinch_event_record, None)
        mock_logger.error.assert_called_once_with("No registered event for correlation_id %s", '12345')
