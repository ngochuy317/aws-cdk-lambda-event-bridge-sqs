from common.constants import get_logger
import json

# Set up logging
logger = get_logger()


def lambda_handler(event, context):

    logger.info(f"Received event: {event} with context: {context}")

    for record in event['Records']:
        try:
            # Parse the SQS message body
            message = json.loads(record['body'])
            transformed_data = {
                "transaction_correlation_id": message.get("transaction_correlation_id"),
                "from": message.get("from"),
                "to": message.get("to"),
                "sms_message": message.get("sms_message"),
                "sms_message_id": message.get("sms_message_id"),
                "event_timestamp": message.get("event_timestamp"),
                "event_type": message.get("event_type"),
                "source_sender": message.get("source_sender"),
            }

            # Adding additional metadata (as an example, hard-coded values for now)
            transformed_data["sms_metadata"] = {
                "application_number": "7777777",
                "lead_number": "8237894"
            }
