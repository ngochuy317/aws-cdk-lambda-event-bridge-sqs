import os
import json
from common.sqs import SqsClient
from common.constants import (
    get_logger,
)

# Set up logging
logger = get_logger()

sqs_client = SqsClient(logger)

ENV_ODS_TO_CLASS_QUEUE_URL = "ODS_TO_CLASS_QUEUE_URL"

def lambda_handler(event, context):

    logger.info(f"Received event: {event} with context: {context}")

    # Process each SQS message
    for record in event['Records']:
        try:
            message = {"eventSourceARN": record["eventSourceARN"]}

            # Send the transformed message to another SQS queue
            sqs_client.send_to_sqs(message, ENV_ODS_TO_CLASS_QUEUE_URL)

        except Exception as e:
            logger.exception(f"Error processing record: {e}")

    