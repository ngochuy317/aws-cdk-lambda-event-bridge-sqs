import json
from decimal import Decimal
import os
import boto3
from datetime import datetime
from sinch_message_delivery_webhook.const import get_logger

REQUEST_LOG_TABLE = os.environ['REQUEST_LOG_TABLE']
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

    for sinch_event in event["Records"]:
        event_to_process = json.loads(sinch_event['body'].replace('\\"', '"').replace('\\"', '\"'))
        logger.debug("Processing event: %s", event_to_process)
        logger.info("Processing %s event", event_to_process["correlation_id"])

        # Sending original message for communication history
        post_event(event_to_process, 'original_delivery_receipt')

        if check_bot_entries(event_to_process):
            logger.warn("Skipping event due to bot entries: %s", event_to_process)
            continue

        logged_event = get_logged_event(event_to_process)
        logger.debug("Logged event: %s", logged_event)

        if not bool(logged_event):
            logger.error("No registered event for %s", event_to_process['correlation_id'])
            raise Exception(f"No registered event for {event_to_process['correlation_id']}")

        prepared_event = prepare_db_event(logged_event, event_to_process)
        logger.debug("Prepared event: %s", prepared_event)

        if prepared_event:
            request_log.put_item(Item=prepared_event)
            post_event(prepared_event)
            logger.info("Successfully saved %s with status %s", event_to_process["correlation_id"], event_to_process["message_delivery_report"]["status"])
        else:
            # This can be a retry, so we will re-post the event with duplication mark
            # Consumer system will decide if they want to process possibly duplicated events or not
            post_event(logged_event | {
                'duplicate_event': True
            })
            logger.warning("Outdated event %s with status %s!", event_to_process['correlation_id'], event_to_process["message_delivery_report"]["status"])

    return {
        'statusCode': 200,
        'body': json.dumps('OK')
    }

def prepare_db_event(db_event, sinch_response):
    logger.debug("Preparing DB event with db_event: %s and sinch_response: %s", db_event, sinch_response)
    final_event = None

    if db_event['last_update_ts'] < sinch_response['event_time']:
        final_event = db_event | {
            'last_update_ts': sinch_response['event_time'],
            'event_status': sinch_response['message_delivery_report']['status'],
            sinch_response['message_delivery_report']['status']: sinch_response
        }
    elif (sinch_response['message_delivery_report']['status'] in db_event) and (db_event[sinch_response['message_delivery_report']['status']]['event_time'] < sinch_response['event_time']):
        logger.warning("Generally outdated %s event, but the status field is behind this event date!", sinch_response["correlation_id"])
        final_event = db_event | {
            sinch_response['message_delivery_report']['status']: sinch_response
        }

    logger.debug("Final event prepared: %s", final_event)
    return final_event

def get_logged_event(event):
    logger.debug("Getting logged event for event: %s", event)
    key = {
        'unique_request_id': event['correlation_id']
    }
    response = request_log.get_item(Key=key)
    logger.debug("Response from get_item: %s", response)

    if 'Item' in response:
        return response['Item']

    return None

def post_event(event, detail_type='message_delivery_receipt'):
    logger.debug("Posting event: %s", event)
    event_bridge_client.put_events(
        Entries=[
            {
                'Time': datetime.today(),
                'Source': 'SINCH_MESSAGE_DELIVERY_WEBHOOK',
                'Resources': [],
                'DetailType': detail_type,
                'Detail': json.dumps(event, cls=DecimalEncoder),
                'EventBusName': os.environ['SMS_EVENT_BUS']
            },
        ]
    )

def check_bot_entries(event):
    logger.debug("Checking for bot entries in event: %s", event)
    metadata = event.get('message_delivery_report', {}).get('metadata')
    logger.debug("Metadata extracted: %s", metadata)

    if metadata:
        logger.debug("Metadata exists, proceeding to load JSON.")
        metadata_dict = json.loads(metadata)
        logger.debug("Metadata after JSON load: %s", metadata_dict)

        chl_bot_id = metadata_dict.get('chl_bot_id')
        chl_bot_version = metadata_dict.get('chl_bot_version')
        logger.debug("chl_bot_id: %s, chl_bot_version: %s", chl_bot_id, chl_bot_version)

        if chl_bot_id and chl_bot_version:
            logger.info(f"Found bot entry with chl_bot_id: {chl_bot_id} and chl_bot_version: {chl_bot_version}. Skipping event processing.")
            return True
        else:
            logger.debug("chl_bot_id and/or chl_bot_version not found in metadata.")
    else:
        logger.debug("No metadata found in event.")

    logger.debug("No bot entries found, returning False.")
    return False