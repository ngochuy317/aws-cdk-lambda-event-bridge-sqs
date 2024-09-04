import os
import json
from common.rds_data_client import RDSDataClient
from common.constants import (
    ENV_ODS_DB_CLUSTER_ARN,
    ENV_ODS_DB_SECRET_ARN,
    ENV_ODS_DB_NAME,
    get_logger,
)

# Set up logging
logger = get_logger()

rds_data_client = RDSDataClient()

cluster_arn = os.environ[ENV_ODS_DB_CLUSTER_ARN]
secret_arn = os.environ[ENV_ODS_DB_SECRET_ARN]
db_name = os.environ[ENV_ODS_DB_NAME]

def lambda_handler(event, context):

    # Process each SQS message
    for record in event['Records']:
        try:
            message_body = json.loads(record['body'])
            logger.info(f"Processing message: {message_body}")

            # Example SQL query to fetch data from the PostgreSQL database
            query = "SELECT * FROM users"
            parameters = []

            # Execute the SQL query
            result = rds_data_client.execute_statement(query, parameters, cluster_arn, secret_arn, db_name)

            # Process the result (example: log the result)
            logger.info(f"Query result: {result}")

        except Exception as e:
            logger.exception(f"Error processing record: {e}")
