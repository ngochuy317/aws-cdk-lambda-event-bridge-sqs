import json
from decimal import Decimal
import os
import boto3
from datetime import datetime
from sinch_message_delivery_webhook.const import get_logger

# Environment variables and initialization
REQUEST_LOG_TABLE = os.getenv('REQUEST_LOG_TABLE')
if not REQUEST_LOG_TABLE:
    raise EnvironmentError("Environment variable REQUEST_LOG_TABLE is required.")
SMS_EVENT_BUS = os.getenv('SMS_EVENT_BUS')
if not SMS_EVENT_BUS:
    raise EnvironmentError("Environment variable SMS_EVENT_BUS is required.")

request_log = boto3.resource('dynamodb').Table(REQUEST_LOG_TABLE)
event_bridge_client = boto3.client('events')
logger = get_logger()

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

def lambda_handler(event, context):
    logger.debug("Lambda handler started with event: %s", event)

    if "Records" not in event:
        logger.error("No 'Records' found in the event.")
        return {'statusCode': 400, 'body': 'Invalid event structure'}

    for sinch_event in event["Records"]:
        try:
            event_to_process = json.loads(sinch_event.get('body', '{}').replace('\\"', '"').replace('\\"', '\"'))
            logger.debug("Processing event: %s", event_to_process)
            if "correlation_id" not in event_to_process:
                logger.error("Event missing 'correlation_id': %s", event_to_process)
                continue

            post_event(event_to_process, 'original_delivery_receipt')
            if check_bot_entries(event_to_process):
                logger.warning("Skipping event due to bot entries: %s", event_to_process)
                continue

            logged_event = get_logged_event(event_to_process)
            if not logged_event:
                logger.error("No registered event for correlation_id %s", event_to_process['correlation_id'])
                continue

            prepared_event = prepare_db_event(logged_event, event_to_process)
            if prepared_event:
                request_log.put_item(Item=prepared_event)
                post_event(prepared_event)
                logger.info("Successfully saved %s with status %s", event_to_process["correlation_id"], event_to_process.get("message_delivery_report", {}).get("status"))
            else:
                post_event(logged_event | {'duplicate_event': True})
                logger.warning("Outdated event %s with status %s", event_to_process['correlation_id'], event_to_process.get("message_delivery_report", {}).get("status"))
        
        except json.JSONDecodeError as e:
            logger.error("Error decoding JSON: %s", e)
        except KeyError as e:
            logger.error("Missing required key: %s", e)
        except Exception as e:
            logger.exception("An unexpected error occurred: %s", e)

    return {'statusCode': 200, 'body': json.dumps('OK')}

def prepare_db_event(db_event, sinch_response):
    logger.debug("Preparing DB event with db_event: %s and sinch_response: %s", db_event, sinch_response)

    if not all(key in sinch_response for key in ['event_time', 'message_delivery_report']):
        logger.error("Invalid sinch_response format: %s", sinch_response)
        return None

    event_time = sinch_response['event_time']
    status = sinch_response['message_delivery_report']['status']
    if db_event.get('last_update_ts', 0) < event_time:
        return db_event | {'last_update_ts': event_time, 'event_status': status, status: sinch_response}

    if status in db_event and db_event[status].get('event_time', 0) < event_time:
        logger.warning("Updating outdated %s event with newer data.", sinch_response["correlation_id"])
        return db_event | {status: sinch_response}

    logger.debug("No update required for event.")
    return None

def get_logged_event(event):
    correlation_id = event.get('correlation_id')
    if not correlation_id:
        logger.error("Event missing 'correlation_id': %s", event)
        return None

    try:
        response = request_log.get_item(Key={'unique_request_id': correlation_id})
        return response.get('Item')
    except Exception as e:
        logger.exception("Failed to get item from DynamoDB: %s", e)
        return None

def post_event(event, detail_type='message_delivery_receipt'):
    logger.debug("Posting event: %s", event)
    try:
        event_bridge_client.put_events(
            Entries=[{
                'Time': datetime.utcnow(),
                'Source': 'SINCH_MESSAGE_DELIVERY_WEBHOOK',
                'Resources': [],
                'DetailType': detail_type,
                'Detail': json.dumps(event, cls=DecimalEncoder),
                'EventBusName': SMS_EVENT_BUS
            }]
        )
    except Exception as e:
        logger.exception("Failed to post event to EventBridge: %s", e)

def check_bot_entries(event):
    metadata_str = event.get('message_delivery_report', {}).get('metadata')
    if not metadata_str:
        logger.debug("No metadata in event.")
        return False

    try:
        metadata = json.loads(metadata_str)
        if metadata.get('chl_bot_id') and metadata.get('chl_bot_version'):
            logger.info("Bot entry detected, skipping event.")
            return True
    except json.JSONDecodeError as e:
        logger.error("Failed to decode metadata JSON: %s", e)
    
    return False