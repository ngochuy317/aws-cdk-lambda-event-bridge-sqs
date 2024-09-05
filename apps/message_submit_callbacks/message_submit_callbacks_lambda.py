import os
import json
from common.constants import get_logger
from common.event_bridge import EventBridge

# Set up logging
logger = get_logger()
event_bridge_client = EventBridge()
event_bus_name = os.environ['EVENT_BUS_NAME']


def handler(event, context):
    logger.info(f"event: {event}")
    for record in event['Records']:
        try:
            # Parse the SQS message body
            message = json.loads(record['body'])
            logger.info(f"message: {message}")
            
            # Validate the message content
            message_submit_notification = message.get("message_submit_notification", {})
            message_id = message_submit_notification.get("message_id")
            conversation_id = message_submit_notification.get("conversation_id")
            if not message_id or not conversation_id:
                raise ValueError("Message must contain 'message_id' and 'conversation_id'")
            
            # Further processing logic here...
            logger.info(f"Processing message with ID: {message_id} and conversation ID: {conversation_id}")

            res = event_bridge_client.put_events(event_bus_name, "message-submit", message)
            logger.info(f"response: {res}")

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
