import boto3
from botocore.exceptions import ClientError


class SQSClient:
    def __init__(self):
        self.sqs_client = boto3.client('sqs')

    def send_message_to_sqs(self, queue_url, message, message_group_id):
        """Send a message to an SQS queue."""
        try:
            response = self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=message,
                MessageGroupId=message_group_id  # Required for FIFO queues
            )
            print(f"Message sent to SQS: {response['MessageId']}")
        except ClientError as e:
            print(f"Error sending message to SQS: {e}")
            raise e
