import json
import os
import traceback
import boto3
from datetime import datetime
from botocore.exceptions import NoCredentialsError, ClientError
from sinch_proxy.const import (
    ENV_LAMBDA_REQUEST_LOG_TABLE,
    ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH,
    ENV_REFRESH_INTERVAL_MINUTES,
    get_global_environment,
    get_logger
)
from sinch_proxy.service.sinch_service import SinchService
from sinch_proxy.service.ssm_service import SSMService

# Constants and Globals
REQUEST_LOG_TABLE = os.environ[ENV_LAMBDA_REQUEST_LOG_TABLE]

# TTL (Time To Live) logic for locking objects:
# 1. New event enters Lambda.
# 2. Check if a corresponding DynamoDB item exists; if yes, raise Exception.
# 3. Create a DynamoDB item with a 5-minute TTL (lock) to handle failures.
# 4. Process the event.
# 5. Update the item with processed info and extend TTL to 30 days.
PROCESSING_TTL = 5 * 60  # 5 minutes
EVENT_TTL = 30 * 24 * 60 * 60  # 30 days

logger = get_logger()
ssm_service = SSMService(get_global_environment(), logger)

# Instantiate SinchService
try:
    sinch_service = SinchService(
        logger=logger,
        ssm_service=ssm_service,
        client_credential_path=os.getenv(ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH),
        refresh_interval_minutes=int(os.getenv(ENV_REFRESH_INTERVAL_MINUTES, 15))
    )
except Exception as e:
    logger.exception("Failed to initialize SinchService: %s", e)
    raise

# Initialize DynamoDB resource and table
try:
    request_log = boto3.resource('dynamodb').Table(REQUEST_LOG_TABLE)
except NoCredentialsError as e:
    logger.exception("DynamoDB credentials not found: %s", e)
    raise
except Exception as e:
    logger.exception("Failed to connect to DynamoDB table %s: %s", REQUEST_LOG_TABLE, e)
    raise

def lambda_handler(event, context):
    logger.debug("Received event: %s", event)
    batch_item_failures = []

    for acs_event in event["Records"]:
        try:
            event_to_process = parse_event_body(acs_event.get('body', '{}'))
            if not event_to_process:
                raise ValueError("Parsed event body is empty or invalid")

            for single_event in event_to_process.get("data", []):
                process_single_event(single_event)

        except Exception as e:
            print(traceback.format_exc())
            logger.error("Failed to process message ID %s due to %s", acs_event.get('messageId'), e)
            batch_item_failures.append({"itemIdentifier": acs_event.get('messageId')})

    return {
        'statusCode': 200,
        'body': json.dumps('OK'),
        'batchItemFailures': [{'itemIdentifier': failure['itemIdentifier']} for failure in batch_item_failures]
    }

def process_single_event(single_event):
    try:
        logger.info("Starting to process %s", single_event['unique_request_id'])
        processed_event = get_processed_event(single_event)

        if processed_event:
            if processed_event['event_status'] == 'MA_PROCESSING':
                logger.warning("Event %s has already been processed in MA_PROCESSING status!", single_event['unique_request_id'])
                raise Exception('Event already processed!')
            logger.info("Event %s has already been processed in %s status!", single_event['unique_request_id'], processed_event['event_status'])
            return

        process_event(single_event)

    except Exception as e:
        logger.exception("Error processing single event %s: %s", single_event.get('unique_request_id'), e)
        raise

def process_event(event):
    db_event = log_processing_event(event)

    try:
        sms_code = event.get('short_code')
        if not sms_code:
            raise ValueError(f"Missing mandatory parameter: 'short_code'. Current value: {sms_code}")

        sinch_response = sinch_service.post_message(
            conversation_metadata=retrieve_conversation_metadata(event),
            unique_request_id=event["unique_request_id"],
            phone_number=event["phone_number"],
            sms_code=sms_code,
            message_body=event["message_body"]
        )

        log_processed_event(db_event, sinch_response)
        logger.info("Successfully sent event %s to %s", event["unique_request_id"], sms_code)

    except Exception as e:
        logger.exception("Failed to process event %s: %s", event['unique_request_id'], e)
        raise

def retrieve_conversation_metadata(event):
    try:
        conversation_metadata = {k.replace('c_meta_', ''): v for k, v in event.items() if k.startswith('c_meta_')}
        if 'message_body' not in event:
            raise ValueError("Event is missing 'message_body' field")
        conversation_metadata['message_body'] = event['message_body']
        return conversation_metadata
    except Exception as e:
        logger.exception("Error retrieving conversation metadata: %s", e)
        raise

def log_processing_event(event):
    try:
        db_event = {
            'unique_request_id': event['unique_request_id'],
            'acs_data': event,
            'event_status': 'MA_PROCESSING',
            'expire_ts': str(int(datetime.now().timestamp()) + PROCESSING_TTL)
        }

        logger.info("Logging event %s with status %s", event['unique_request_id'], db_event['event_status'])
        request_log.put_item(Item=db_event)
        return db_event

    except ClientError as e:
        logger.exception("Failed to log processing event for %s: %s", event['unique_request_id'], e)
        raise
    except Exception as e:
        logger.exception("Unexpected error logging processing event for %s: %s", event['unique_request_id'], e)
        raise

def log_processed_event(db_event, sinch_response):
    try:
        logger.debug("Before updating, db_event: %s", db_event)

        processed_db_event = {
            **db_event,
            'message_id': sinch_response['message_id'],
            'SINCH_ACCEPTED': sinch_response,
            'event_status': 'SINCH_ACCEPTED',
            'last_update_ts': sinch_response['accepted_time'],
            'expire_ts': str(int(datetime.now().timestamp()) + EVENT_TTL)
        }

        logger.debug("After updating, processed_db_event: %s", processed_db_event)
        request_log.put_item(Item=processed_db_event)
        logger.info("Event %s logged with status %s", processed_db_event['unique_request_id'], processed_db_event['event_status'])
        return processed_db_event

    except ClientError as e:
        logger.exception("Failed to log processed event for %s: %s", db_event['unique_request_id'], e)
        raise
    except Exception as e:
        logger.exception("Unexpected error logging processed event for %s: %s", db_event['unique_request_id'], e)
        raise

def get_processed_event(event):
    try:
        response = request_log.get_item(Key={'unique_request_id': event['unique_request_id']})
        if 'Item' in response and int(response['Item']['expire_ts']) > int(datetime.now().timestamp()):
            return response['Item']
        return None
    except ClientError as e:
        logger.exception("Failed to retrieve processed event for %s: %s", event['unique_request_id'], e)
        raise
    except Exception as e:
        logger.exception("Unexpected error retrieving processed event for %s: %s", event['unique_request_id'], e)
        raise

def parse_event_body(body):
    try:
        return json.loads(body.replace('\\"', '"').replace('\\\\', '\\').replace('\\\'', '\''))
    except json.JSONDecodeError as e:
        logger.error("JSON decoding failed for body: %s", e)
        return {}
    except Exception as e:
        logger.exception("Unexpected error parsing event body: %s", e)
        return {}