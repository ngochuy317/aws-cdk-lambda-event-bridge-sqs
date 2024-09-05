import boto3
import os
import json


class EventBridge:
    def __init__(self):
        self.event_bridge = boto3.client('events')
        self.source = os.environ['AWS_LAMBDA_FUNCTION_NAME']

    def put_events(self, event_bus, detail_type, message):
        response = self.event_bridge.put_events(
            Entries=[{
                'Source': self.source,
                'DetailType': detail_type,
                'Detail': json.dumps(message),
                'EventBusName': event_bus
            }]
        )
        return response
