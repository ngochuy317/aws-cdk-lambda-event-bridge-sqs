from common.constants import get_logger
import json

# Set up logging
logger = get_logger()


def lambda_handler(event, context):

    for record in event["Records"]:
        event_bridge_event = json.loads(record['body'])
        logger.info(f"Received event: {event_bridge_event} with context: {context}")
