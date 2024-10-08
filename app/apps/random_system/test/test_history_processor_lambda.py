import os
from common.constants import (
    ENV_RANDOM_SYSTEM_DB_CLUSTER_ARN,
    ENV_RANDOM_SYSTEM_DB_SECRET_ARN,
    ENV_RANDOM_SYSTEM_DB_NAME,
    ENV_RANDOM_SYSTEM_OUTPUT_QUEUE_URL,
)
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ[ENV_RANDOM_SYSTEM_DB_CLUSTER_ARN] = 'arn:aws:rds:us-west-2:123456789012:cluster:mydbcluster'
os.environ[ENV_RANDOM_SYSTEM_DB_SECRET_ARN] = 'arn:aws:secretsmanager:us-west-2:123456789012:secret:mysecret'
os.environ[ENV_RANDOM_SYSTEM_DB_NAME] = 'mydatabase'
os.environ[ENV_RANDOM_SYSTEM_OUTPUT_QUEUE_URL] = 'ENV_RANDOM_SYSTEM_OUTPUT_QUEUE_URL'

from unittest.mock import patch
import json
from random_system.history_processor_lambda import lambda_handler

@patch('random_system.history_processor_lambda.transform_message')
@patch('random_system.history_processor_lambda.sqs_client')
@patch('random_system.history_processor_lambda.rds_data_client')
def test_lambda_handler(mock_rds_data_client, mock_sqs_client, mock_transform_message):
    
    sample_event = {
        'Records': [
            {
                'body': json.dumps({'id': 1})
            }
        ]
    }
    
    lambda_handler(sample_event, None)

    mock_transform_message.assert_called()