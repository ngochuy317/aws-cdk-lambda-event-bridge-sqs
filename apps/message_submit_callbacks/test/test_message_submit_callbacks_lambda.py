from unittest.mock import patch
import os
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_LAMBDA_FUNCTION_NAME'] = 'AWS_LAMBDA_FUNCTION_NAME'
os.environ['EVENT_BUS_NAME'] = 'MyCustomEventBus'
import json
from apps.message_submit_callbacks.message_submit_callbacks_lambda import handler


@patch('message_submit_callbacks.message_submit_callbacks_lambda.event_bridge_client')
def test_handler_valid_message(mock_event_bridge_client):
    # Arrange

    mock_event_bridge_client_instance = mock_event_bridge_client.return_value
    mock_event_bridge_client_instance.put_events.return_value = {"Status": "Success"}

    # Create a sample SQS event payload with a valid message
    sample_event = {
        "Records": [
            {
                "body": json.dumps({
                    "message_submit_notification": {
                        "message_id": "01J4SPT56K2T1ZK9W4VWWA1DGV",
                        "conversation_id": "01J4SPT58WZ17PEZD0BEABJHZ5",
                        "text": "Hello, this is a test message.",
                        "metadata": {
                            "unique_request_id": "f6047b60-7785-456d-a70d-a39a71b09686"
                        }
                    }
                })
            }
        ]
    }

    # Act
    handler(sample_event, None)

    # Assert
    mock_event_bridge_client_instance.put_events.assert_called_once_with(
        'MyCustomEventBus', "message-submit", json.loads(sample_event['Records'][0]['body'])
    )

@patch('message_submit_callbacks.message_submit_callbacks_lambda.event_bridge_client')
def test_handler_invalid_message(self, mock_event_bridge_client):

    mock_event_bridge_instance = mock_event_bridge_client.return_value

    # Create a sample SQS event payload with an invalid message (missing message_id)
    sample_event = {
        "Records": [
            {
                "body": json.dumps({
                    "message_submit_notification": {
                        "conversation_id": "01J4SPT58WZ17PEZD0BEABJHZ5",
                        "text": "Hello, this is a test message.",
                        "metadata": {
                            "unique_request_id": "f6047b60-7785-456d-a70d-a39a71b09686"
                        }
                    }
                })
            }
        ]
    }

    # Act
    handler(sample_event, None)

    # Assert
    mock_event_bridge_instance.put_events.assert_not_called()

