import boto3
import logging
from datetime import datetime
import pytz
import json
import os

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize the boto3 client for interacting with SQS
sqs = boto3.client('sqs')

# Timezone mappings based on the last three characters of the queue name
TIMEZONE_MAP = {
    'EST': 'America/New_York',
    'CST': 'America/Chicago',
    'MST': 'America/Denver',
    'PST': 'America/Los_Angeles',
    'EDT': 'America/New_York',
    'CDT': 'America/Chicago',
    'MDT': 'America/Denver',
    'PDT': 'America/Los_Angeles'
}


def get_current_timezone(queue_name):
    """Get the timezone based on the last three characters of the queue name."""
    # Remove the ".fifo" suffix if the queue name ends with it
    if queue_name.endswith(".fifo"):
        queue_name = queue_name[:-5]  # Remove the last 5 characters (".fifo")

    timezone_code = queue_name[-3:].upper()  # Convert the last three characters to uppercase
    timezone = TIMEZONE_MAP.get(timezone_code, 'America/New_York')
    if not timezone:
        logger.error(f"Invalid timezone code '{timezone_code}' for queue '{queue_name}'. Skipping.")
    return timezone


def get_current_time(timezone):
    """Get the current time in the specified timezone."""
    tz = pytz.timezone(timezone)
    return datetime.now(tz)


def is_within_eligibility_window(current_time):
    """Check if the current time is within the eligibility window."""
    start_time = current_time.replace(hour=8, minute=0, second=0, microsecond=0)
    end_time = current_time.replace(hour=20, minute=30, second=0, microsecond=0)
    return start_time <= current_time <= end_time


def enable_queue(queue_url):
    """Enable the queue by setting the policy to allow access."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "SQS:SendMessage",
                "Resource": queue_url
            }
        ]
    }
    policy_json = json.dumps(policy)
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            'Policy': policy_json
        }
    )
    logger.info(f"Queue {queue_url} enabled with policy: {policy_json}")


def disable_queue(queue_url):
    """Disable the queue by removing the policy that allows access."""
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            'Policy': ''  # Setting an empty policy effectively disables the queue
        }
    )
    logger.info(f"Queue {queue_url} disabled.")


def lambda_handler(event, context):
    """Lambda function entry point."""
    # Get the queue names from the environment variable
    queue_names_str = os.getenv('QUEUE_NAMES', '')
    queue_names = queue_names_str.split(',')

    for queue_name in queue_names:
        queue_name = queue_name.strip()
        timezone = get_current_timezone(queue_name)

        if not timezone:
            continue  # Skip this queue if the timezone is invalid

        current_time = get_current_time(timezone)

        logger.info(f"Checking queue {queue_name} status at {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        queue_url = f"https://sqs.{os.environ['REGION']}.amazonaws.com/{os.environ['ACCOUNT_ID']}/{queue_name}"
        queue_attributes = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['Policy']
        )
        queue_policy = queue_attributes.get('Attributes', {}).get('Policy', '')
        queue_enabled = bool(queue_policy)
        within_window = is_within_eligibility_window(current_time)
        status = "enable" if queue_enabled else "disable"
        eligibility_window_status = "within" if within_window else "out of"
        logger.info(f"{queue_name} is {status} and is {eligibility_window_status} eligibility window")

        if queue_enabled and not within_window:
            disable_queue(queue_url)
        elif not queue_enabled and within_window:
            enable_queue(queue_url)

    logger.info("Queue policies updated successfully.")
    return {
        'statusCode': 200,
        'body': 'Queue statuses updated successfully.'
    }
