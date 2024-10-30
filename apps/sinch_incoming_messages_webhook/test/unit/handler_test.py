import json
import os
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['EVENT_BUS_SINCH_MESSAGES'] = 'test-event-bus'
os.environ['SINCH_SNS'] = 'arn:aws:sns:region:account-id:test-topic'
import pytest
from unittest.mock import patch
from sinch_incoming_messages_webhook.main import lambda_handler, send_original_message


class TestSinchIncomingMessagesWebhookHandler:

    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_send_original_message_success(self, mock_event_bridge):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}

        processing_event = {"key": "value"}
        send_original_message(processing_event)

        mock_event_bridge.put_events.assert_called_once_with(
            Entries=[{
                'Source': 'SINCH',
                'DetailType': 'original_income_message',
                'Detail': json.dumps(processing_event),
                'EventBusName': 'test-event-bus'
            }]
        )

    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_send_original_message_failure(self, mock_event_bridge):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 1}

        processing_event = {"key": "value"}
        send_original_message(processing_event)

        mock_event_bridge.put_events.assert_called_once()

    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_with_incoming_message(self, mock_event_bridge, mock_sns_client):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}
        mock_sns_client.publish.return_value = {'MessageId': 'test-message-id'}

        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "text_message": {
                            "text": "Hello, World!"
                        },
                    },
                    "id": "message-id-123",
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "sender_id": "sender-123",
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        response = lambda_handler(event, context)

        assert response['statusCode'] == 200
        assert response['body'] == "OK"

        mock_event_bridge.put_events.assert_called_once()
        mock_sns_client.publish.assert_called_once()

    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_missing_message_field(self, mock_event_bridge, mock_sns_client):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}
        mock_sns_client.publish.return_value = {'MessageId': 'test-message-id'}

        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message_redaction": {
                    "contact_message": {
                        "text_message": {
                            "text": "Hello, World!"
                        },
                    },
                    "id": "message-id-123",
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "sender_id": "sender-123",
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        response = lambda_handler(event, context)

        assert response['statusCode'] == 200
        assert response['body'] == "OK"

        mock_event_bridge.put_events.assert_called_once()
        mock_sns_client.publish.assert_called_once()

    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_send_original_message_exception(self, mock_event_bridge):
        mock_event_bridge.put_events.side_effect = Exception("Test Exception")

        processing_event = {"key": "value"}

        send_original_message(processing_event)

        mock_event_bridge.put_events.assert_called_once()

    @patch('sinch_incoming_messages_webhook.main.logger')
    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_with_exception_in_put_events(self, mock_event_bridge, mock_sns_client, mock_logger):
        mock_event_bridge.put_events.side_effect = Exception("EventBridge Error")

        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "text_message": {
                            "text": "Hello, World!"
                        },
                    },
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "id": "message-id-123",
                    "sender_id": "sender-123"
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}  # Mocked context

        # Call the lambda_handler and verify that it handles the exception
        response = lambda_handler(event, context)

        # Ensure the response is still successful even if an internal error occurred
        assert response['statusCode'] == 200
        assert response['body'] == "OK"

        mock_event_bridge.put_events.assert_called_once()
        mock_sns_client.publish.assert_called_once()
        mock_logger.exception.assert_called_once_with("Exception occurred while sending message to Event Bridge: EventBridge Error")

    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_with_exception_in_publish(self, mock_event_bridge, mock_sns_client):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}
        # Simulate an exception being raised by the publish method
        mock_sns_client.publish.side_effect = Exception("SNS Publish Error")

        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "text_message": {
                            "text": "Hello, World!"
                        },
                    },
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "id": "message-id-123",
                    "sender_id": "sender-123"
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        # Call the lambda_handler and verify that it handles the exception
        with pytest.raises(Exception):
            response = lambda_handler(event, context)

            # The response should still be successful, but the publish should have raised an exception
            assert response['statusCode'] == 200
            assert response['body'] == "OK"

        mock_event_bridge.put_events.assert_called_once()
        mock_sns_client.publish.assert_called_once()

    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_invalid_event_format(self, mock_event_bridge, mock_sns_client):
        # Invalid event structure (missing 'body' key)
        event = {
            "resource": "/auth/incoming/messages"
        }
        context = {} 

        # Call the lambda_handler and verify that it handles the missing body gracefully
        response = lambda_handler(event, context)

        # The lambda function should still return a 200 response even if the event is malformed
        assert response['statusCode'] == 400
        assert response['body'] == "Missing 'body' field"

        mock_event_bridge.put_events.assert_not_called()
        mock_sns_client.publish.assert_not_called()

    @patch.dict(os.environ, {'AWS_DEFAULT_REGION': "us-east-1"}, clear=True)
    def test_missing_environment_variables(self):
        with pytest.raises(KeyError):
            import importlib
            import sinch_incoming_messages_webhook.main as main_module
            importlib.reload(main_module)

    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_with_media_card_message(self, mock_event_bridge, mock_sns_client):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}
        mock_sns_client.publish.return_value = {'MessageId': 'test-message-id'}

        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "media_card_message": {
                            "caption": "This is a media card"
                        }
                    },
                    "id": "message-id-123",
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "sender_id": "sender-123",
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        response = lambda_handler(event, context)

        assert response['statusCode'] == 200
        assert response['body'] == "OK"

        mock_event_bridge.put_events.assert_called_once()
        mock_sns_client.publish.assert_called_once()
    
    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_with_media_message(self, mock_event_bridge, mock_sns_client):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}
        mock_sns_client.publish.return_value = {'MessageId': 'test-message-id'}

        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "media_message": {
                            "url": "https://example.com/media"
                        }
                    },
                    "id": "message-id-123",
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "sender_id": "sender-123",
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        response = lambda_handler(event, context)

        assert response['statusCode'] == 200
        assert response['body'] == "OK"

        mock_event_bridge.put_events.assert_called_once()
        mock_sns_client.publish.assert_called_once()

    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_with_missing_required_fields(self, mock_event_bridge, mock_sns_client):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}
        mock_sns_client.publish.return_value = {'MessageId': 'test-message-id'}

        # Missing 'id' field
        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "text_message": {
                            "text": "Hello, World!"
                        }
                    },
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "sender_id": "sender-123",
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        response = lambda_handler(event, context)

        assert response['statusCode'] == 400
        assert "Missing field in message" in response['body']

        mock_sns_client.publish.assert_not_called()
    
    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_with_unknown_message_type(self, mock_event_bridge, mock_sns_client):
        mock_event_bridge.put_events.return_value = {'FailedEntryCount': 0}
        mock_sns_client.publish.return_value = {'MessageId': 'test-message-id'}

        event = {
            "resource": "/auth/incoming/messages",
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "unknown_message_type": {
                            "content": "Some unknown content"
                        }
                    },
                    "id": "message-id-123",
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "sender_id": "sender-123",
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        response = lambda_handler(event, context)

        assert response['statusCode'] == 200
        assert response['body'] == "OK"

        mock_event_bridge.put_events.assert_called_once()
        mock_sns_client.publish.assert_called_once()
    
    @patch('sinch_incoming_messages_webhook.main.sns_client')
    @patch('sinch_incoming_messages_webhook.main.event_bridge')
    def test_lambda_handler_missing_event_resource(self, mock_event_bridge, mock_sns_client):
        # Event missing 'resource' key
        event = {
            "body": json.dumps({
                "message": {
                    "contact_message": {
                        "text_message": {
                            "text": "Hello, World!"
                        }
                    },
                    "id": "message-id-123",
                    "channel_identity": {
                        "identity": "user@example.com"
                    },
                    "sender_id": "sender-123",
                },
                "event_time": "2024-10-26T12:00:00Z"
            })
        }
        context = {}

        response = lambda_handler(event, context)

        assert response['statusCode'] == 404
        assert response['body'] == "Resource not found"

        mock_event_bridge.put_events.assert_not_called()
        mock_sns_client.publish.assert_not_called()
