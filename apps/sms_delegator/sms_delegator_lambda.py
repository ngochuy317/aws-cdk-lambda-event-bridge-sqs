import json
import os
import uuid
import boto3
from common.constants import get_logger

logger = get_logger()


def handler(event, context):
    logger.info(f"event: {event}")
    try:
        body = json.loads(event['body'])
        logger.info(f"parsed body: {body}")

        for record in body['Records']:
            message = json.loads(record['body'])
            logger.info(f"message: {message}")
            if isinstance(message, str):
                filtered_message = ''.join(c.lower() for c in message if c.isalpha())
                logger.info(f"filtered_message: {filtered_message}")
                dynamodb = boto3.resource('dynamodb')
                table_name = os.environ.get('TABLE_NAME')
                table = dynamodb.Table(table_name)

                item = {
                    'id': str(uuid.uuid4()),
                    'message': filtered_message
                }
                table.put_item(Item=item)
                logger.info(f"Inserted item into DynamoDB: {item}")


    except Exception as e:
        logger.exception(f"Error processing message: {e}")
