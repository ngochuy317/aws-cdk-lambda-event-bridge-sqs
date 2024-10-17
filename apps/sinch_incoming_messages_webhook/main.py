import os
import json
import boto3


client = boto3.client('sns')
event_bridge = boto3.client('events')
sinch_event_bus_name = os.environ['EVENT_BUS_SINCH_MESSAGES']

def send_original_message(processing_event):
    try:
        response = event_bridge.put_events(
            Entries=[{
                'Source': 'SINCH',
                'DetailType': 'original_income_message',
                'Detail': json.dumps(processing_event),
                'EventBusName': sinch_event_bus_name
            }]
        )
        if response.get('FailedEntryCount') != 0:
            print(f"Error sending message to Event Bridge {response}")
    except Exception as err:
        print(f"Error sending message to Event Bridge {err}")


def lambda_handler(event, context):
    print(event)
    if event["resource"] == "/auth/incoming/messages":
        processing_event = json.loads(event["body"])

        # Sending original message for communication history
        send_original_message(processing_event)

        message_field = "message"

        if "message" not in processing_event:
            message_field = "message_redaction"

        operator_id = ""
        message_body = ""

        try:
            if "metadata" in processing_event[message_field]:
                operator_id = json.loads(processing_event[message_field]["metadata"])["operator"]
        except Exception as err:
            print(err)

        if "media_card_message" in processing_event[message_field]["contact_message"]:
            message_body = processing_event[message_field]["contact_message"]["media_card_message"]["caption"]

        if "media_message" in processing_event[message_field]["contact_message"]:
            message_body = processing_event[message_field]["contact_message"]["media_message"]["url"]

        if "text_message" in processing_event[message_field]["contact_message"]:
            message_body = processing_event[message_field]["contact_message"]["text_message"]["text"]

        local_event = {
            "body": message_body,
            "from": processing_event[message_field]["channel_identity"]["identity"],
            "id": processing_event[message_field]["id"],
            "operator_id": operator_id,
            "received_at": processing_event["event_time"],
            "to": processing_event[message_field]["sender_id"],
            "type": "mo_text"
        }

        print(local_event)
        response = client.publish(
            TargetArn=os.environ['SINCH_SNS'],
            Message=json.dumps({'default': json.dumps(local_event)}),
            MessageStructure='json'
        )

    return {
        'statusCode': 200,
        'body': "OK"
    }
