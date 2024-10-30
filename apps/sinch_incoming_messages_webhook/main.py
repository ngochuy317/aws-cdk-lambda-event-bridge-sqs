import os
import json
import boto3
from sinch_incoming_messages_webhook.const import get_logger

logger = get_logger()

try:
    sns_client = boto3.client('sns')
    event_bridge = boto3.client('events')
    sinch_event_bus_name = os.environ['EVENT_BUS_SINCH_MESSAGES']
except KeyError as e:
    logger.critical(f"Environment variable {str(e)} not found. Unable to initialize.")
    raise

def send_original_message(processing_event):
    if not isinstance(processing_event, dict):
        logger.error("Invalid processing_event format. Expected a dictionary.")
        return

    try:
        response = event_bridge.put_events(
            Entries=[{
                'Source': 'SINCH',
                'DetailType': 'original_income_message',
                'Detail': json.dumps(processing_event),
                'EventBusName': sinch_event_bus_name
            }]
        )
        if response.get('FailedEntryCount', 1) != 0:  # Default to 1 if key is missing
            logger.error(f"Failed to send message to Event Bridge. Response: {response}")
    except Exception as err:
        logger.exception(f"Exception occurred while sending message to Event Bridge: {err}")

def lambda_handler(event, context):
    if not isinstance(event, dict):
        logger.error("Event must be a dictionary.")
        return {
            'statusCode': 400,
            'body': "Invalid event format"
        }

    logger.info("Received event: %s", event)
    
    resource = event.get("resource")
    if resource != "/auth/incoming/messages":
        logger.warning("Unhandled resource: %s", resource)
        return {
            'statusCode': 404,
            'body': "Resource not found"
        }

    try:
        body = event.get("body")
        if not body:
            logger.error("Missing 'body' in event.")
            return {
                'statusCode': 400,
                'body': "Missing 'body' field"
            }
        processing_event = json.loads(body)
    except (TypeError, json.JSONDecodeError) as err:
        logger.exception("Error parsing the 'body' of the event.")
        return {
            'statusCode': 400,
            'body': "Invalid JSON format in 'body'"
        }

    # Sending original message for communication history
    send_original_message(processing_event)

    message_field = "message"
    if "message" not in processing_event:
        message_field = "message_redaction"
        if message_field not in processing_event:
            logger.error("Neither 'message' nor 'message_redaction' is present in processing_event.")
            return {
                'statusCode': 400,
                'body': "Missing message content"
            }

    operator_id = ""
    message_body = ""

    # Extract operator ID from metadata, if present
    try:
        metadata = processing_event.get(message_field, {}).get("metadata", "")
        if metadata:
            operator_data = json.loads(metadata)
            operator_id = operator_data.get("operator", "")
    except (TypeError, json.JSONDecodeError, KeyError) as err:
        logger.warning("Failed to parse operator ID from metadata: %s", err)

    # Extract message content
    contact_message = processing_event.get(message_field, {}).get("contact_message", {})
    if not isinstance(contact_message, dict):
        logger.error("Invalid 'contact_message' format. Expected a dictionary.")
        return {
            'statusCode': 400,
            'body': "Invalid contact message format"
        }

    message_body = ""

    if "media_card_message" in contact_message:
        message_body = contact_message["media_card_message"].get("caption", "")
    if "media_message" in contact_message:
        message_body = contact_message["media_message"].get("url", "")
    if "text_message" in contact_message:
        message_body = contact_message["text_message"].get("text", "")

    # Validate required fields for local event creation
    try:
        local_event = {
            "body": message_body,
            "from": processing_event[message_field]["channel_identity"]["identity"],
            "id": processing_event[message_field]["id"],
            "operator_id": operator_id,
            "received_at": processing_event["event_time"],
            "to": processing_event[message_field]["sender_id"],
            "type": "mo_text"
        }
    except KeyError as err:
        logger.error("Missing required field in processing_event: %s", err)
        return {
            'statusCode': 400,
            'body': f"Missing field in message: {str(err)}"
        }

    logger.info("Local event created: %s", local_event)

    # Publish the local event to SNS
    try:
        sns_response = sns_client.publish(
            TargetArn=os.environ['SINCH_SNS'],
            Message=json.dumps({'default': json.dumps(local_event)}),
            MessageStructure='json'
        )
        logger.info("SNS publish response: %s", sns_response)
    except Exception as err:
        logger.exception("Failed to publish message to SNS: %s", err)
        return {
            'statusCode': 500,
            'body': "Internal server error"
        }

    return {
        'statusCode': 200,
        'body': "OK"
    }
