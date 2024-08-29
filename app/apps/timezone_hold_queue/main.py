from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import os
from common.constants import (
    ENV_START_TIME_HOUR,
    ENV_START_TIME_MINUTE,
    ENV_END_TIME_HOUR,
    ENV_END_TIME_MINUTE,
    ENV_SAFETY_ZONE_START_HOUR,
    ENV_SAFETY_ZONE_START_MINUTE,
    ENV_SAFETY_ZONE_END_HOUR,
    ENV_SAFETY_ZONE_END_MINUTE,
    ENV_HOLIDAY_TABLE_NAME,
    ENV_TARGET_LAMBDA_NAME,
    HOLIDAY_DATE_STR,
)
from common.dynamodb_service import DynamoDBService
from common.lambda_client import LambdaClient

# Set up logging

# Initialize the boto3 client for interacting with SQS
lambda_client = LambdaClient()

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


START_TIME_HOUR = int(os.getenv(ENV_START_TIME_HOUR, '8'))
START_TIME_MINUTE = int(os.getenv(ENV_START_TIME_MINUTE, '0'))
END_TIME_HOUR = int(os.getenv(ENV_END_TIME_HOUR, '20'))
END_TIME_MINUTE = int(os.getenv(ENV_END_TIME_MINUTE, '30'))
SAFETY_ZONE_START_HOUR = int(os.getenv(ENV_SAFETY_ZONE_START_HOUR, '14'))
SAFETY_ZONE_START_MINUTE = int(os.getenv(ENV_SAFETY_ZONE_START_MINUTE, '0'))
SAFETY_ZONE_END_HOUR = int(os.getenv(ENV_SAFETY_ZONE_END_HOUR, '20'))
SAFETY_ZONE_END_MINUTE = int(os.getenv(ENV_SAFETY_ZONE_END_MINUTE, '30'))
TARGET_LAMBDA_NAME = os.getenv(ENV_TARGET_LAMBDA_NAME)
TABLE_NAME = os.getenv(ENV_HOLIDAY_TABLE_NAME)
# holiday_table = DynamoDBService(TABLE_NAME)


def get_current_timezone(queue_name):
    """Get the timezone based on the last three characters of the queue name."""
    # Remove the ".fifo" suffix if the queue name ends with it
    if queue_name.endswith(".fifo"):
        queue_name = queue_name[:-5]  # Remove the last 5 characters (".fifo")

    timezone_code = queue_name[-3:].upper()  # Convert the last three characters to uppercase
    timezone = TIMEZONE_MAP.get(timezone_code)
    return timezone

def is_current_date_holiday():
    return False
    # Format the current date to 'YYYYMMDD'
    current_date = datetime.now().date()
    current_date_str = current_date.strftime('%Y%m%d')
    
    # Get the item from the DynamoDB table
    response = holiday_table.get_item({'HOLIDAY_DATE_CD': current_date_str})
    
    # Check if the item exists in the table
    if 'Item' in response:
        print(f"Today is a holiday: {response['Item'][HOLIDAY_DATE_STR]}")
        return True
    return False

def is_current_time_within_eligibility_window(timezone):
    """Check if the current time is within the eligibility window."""
    try:
        tz = ZoneInfo(timezone)
        current_time = datetime.now(tz)
        start_time = current_time.replace(hour=START_TIME_HOUR, minute=START_TIME_MINUTE, second=0, microsecond=0)
        end_time = current_time.replace(hour=END_TIME_HOUR, minute=END_TIME_MINUTE, second=0, microsecond=0)
    except (ZoneInfoNotFoundError, TypeError) as e:
        print(f"Invalid timezone: {timezone}. Error: {e}")
        est_timezone = ZoneInfo('America/New_York')
        current_time = datetime.now(est_timezone)
        start_time = current_time.replace(hour=SAFETY_ZONE_START_HOUR, minute=SAFETY_ZONE_START_MINUTE, second=0, microsecond=0)
        end_time = current_time.replace(hour=SAFETY_ZONE_END_HOUR, minute=SAFETY_ZONE_END_MINUTE, second=0, microsecond=0)

    # Check if today is a holiday or Sunday
    is_holiday = is_current_date_holiday()
    is_sunday = current_time.weekday() == 6  # 6 corresponds to Sunday

    if is_sunday or is_holiday:
        print(f"Today is {'a Sunday' if is_sunday else 'a holiday'}, outside the eligibility window.")
        return False, current_time

    return start_time <= current_time <= end_time, current_time


def enable_event_source_mapping(uuid):
    """Enable the event source mapping."""
    response = lambda_client.update_event_source_mapping(
        uuid=uuid,
        enabled=True
    )
    print(f"Enabled event source mapping {uuid}: {response}")

def disable_event_source_mapping(uuid):
    """Disable the event source mapping."""
    response = lambda_client.update_event_source_mapping(
        uuid=uuid,
        enabled=False
    )
    print(f"Disabled event source mapping {uuid}: {response}")


def lambda_handler(event, context):
    """Lambda function entry point."""
    response = lambda_client.get_list_event_source_mappings(
        target_lambda_name=TARGET_LAMBDA_NAME
    )
    print(f"Event source mappings: {response}")
    queue_uuid_map = {}
    for mapping in response.get('EventSourceMappings', []):
        if 'sqs' in mapping.get('EventSourceArn'):
            queue_name = mapping['EventSourceArn'].split(':')[-1]
            queue_uuid_map[queue_name] = mapping['UUID']

    print(f"Queue UUID map: {queue_uuid_map}")

    for queue_name, uuid  in queue_uuid_map.items():
        try:
            queue_name = queue_name.strip()
            timezone = get_current_timezone(queue_name)

            within_window, current_time = is_current_time_within_eligibility_window(timezone)


            print(f"Checking event source mapping for {queue_name} at {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            current_mapping = lambda_client.get_event_source_mapping(uuid=uuid)
            mapping_enabled = current_mapping['State'] == 'Enabled'
            status = "enabled" if mapping_enabled else "disabled"
            eligibility_window_status = "within" if within_window else "out of"
            print(f"{queue_name} mapping is {status} and is {eligibility_window_status} eligibility window")

            if mapping_enabled and not within_window:
                disable_event_source_mapping(uuid)
            elif not mapping_enabled and within_window:
                enable_event_source_mapping(uuid)
            else:
                print(f"Queue {queue_name} status is already correct.")
        except Exception as e:
            print(f"Error processing queue {queue_name}: {e}")

    print("Queue policies updated successfully.")
    return {
        'statusCode': 200,
        'body': 'Queue statuses updated successfully.'
    }