import os
import datetime
import json
from common.rds_data_client import RDSDataClient
from common.sqs_client import SQSClient
from common.constants import (
    ENV_ODS_DB_CLUSTER_ARN,
    ENV_ODS_DB_SECRET_ARN,
    ENV_ODS_DB_NAME,
    ENV_ODS_OUTPUT_QUEUE_URL,
    get_logger,
)

# Set up logging
logger = get_logger()

rds_data_client = RDSDataClient()
sqs_client = SQSClient()

cluster_arn = os.environ[ENV_ODS_DB_CLUSTER_ARN]
secret_arn = os.environ[ENV_ODS_DB_SECRET_ARN]
db_name = os.environ[ENV_ODS_DB_NAME]
output_queue_url = os.environ[ENV_ODS_OUTPUT_QUEUE_URL]

def lambda_handler(event, context):

    # Define a default MessageGroupId for the FIFO queue
    message_group_id = 'default-group'

    # Process each SQS message
    for record in event['Records']:
        print("record", record)
        try:
            message_body = json.loads(record['body'])
            logger.info(f"Processing message: {message_body}")

            # Example SQL query to fetch data from the PostgreSQL database
            parameters = []

            current_time = datetime.datetime.now()
            # Insert test data using the RDS Data API
            insert_data_sql = f"""
            INSERT INTO users (name, email) VALUES
            ('name{current_time}', 'name{current_time}@example.com')
            ON CONFLICT (email) DO NOTHING;
            """
            rds_data_client.execute_statement(insert_data_sql, parameters, cluster_arn, secret_arn, db_name)
            print("wafafaf")
            query = "SELECT * FROM users"
            # Execute the SQL query
            result = rds_data_client.execute_statement(query, parameters, cluster_arn, secret_arn, db_name)

            # Process the result (example: log the result)
            logger.info(f"Query result: {result}")

            # Transform the message (example: modify the structure or content)
            transformed_message = transform_message(result["records"])
            logger.info(f"Transformed message: {transformed_message}")

            # Send the transformed message to another SQS queue
            sqs_client.send_message_to_sqs(output_queue_url, transformed_message, message_group_id)

        except Exception as e:
            logger.exception(f"Error processing record: {e}")

def transform_message(query_result):
    """Transform the database query result into a new format."""
    # Example transformation: create a new dictionary from the query result
    transformed_data = {
        "userId": query_result[0][0]['longValue'],
        "userName": query_result[0][1]['stringValue'],
        "userEmail": query_result[0][2]['stringValue']
    }
    return json.dumps(transformed_data)
    