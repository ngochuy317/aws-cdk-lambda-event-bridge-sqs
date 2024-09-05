import boto3
import json
import os


class SqsClient:
    def __init__(self):
        self.sqs = boto3.client('sqs')

    # TODO: switch to regular SQS
    def send_to_fifo_sqs(self, event, queue_key, deduplication_id=None):
        if not deduplication_id:
            deduplication_id = event['unique_key']
        message_group_id = str(hash(event['unique_request_id']) % 10)  # TODO: 10 to constant
        message_body = json.dumps(event)
        self.sqs.send_message(
            QueueUrl=os.getenv(queue_key, ''),
            MessageBody=message_body,
            MessageGroupId=message_group_id,
            MessageDeduplicationId=deduplication_id
        )

    def send_to_sqs(self, event, queue_key, delay=0):
        message_body = json.dumps(event)
        self.sqs.send_message(
            QueueUrl=os.getenv(queue_key, ''),
            MessageBody=message_body,
            DelaySeconds=delay
        )


def get_receive_count(message, logger):
    return get_receive_count_from_message(message['Records'][0], logger)


def get_receive_count_from_message(message, logger):
    string_count = message.get('attributes', {}).get('ApproximateReceiveCount', 1)
    try:
        cnt = int(string_count)
    except BaseException as e:
        logger.error('Invalid record retry count %s, exception %s', string_count, e)
        cnt = 1
    return cnt
