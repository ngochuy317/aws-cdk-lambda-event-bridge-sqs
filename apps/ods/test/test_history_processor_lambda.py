import os
from common.constants import (
    ENV_ODS_DB_CLUSTER_ARN,
    ENV_ODS_DB_SECRET_ARN,
    ENV_ODS_DB_NAME,
    ENV_ODS_OUTPUT_QUEUE_URL,
)
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ[ENV_ODS_DB_CLUSTER_ARN] = 'arn:aws:rds:us-west-2:123456789012:cluster:mydbcluster'
os.environ[ENV_ODS_DB_SECRET_ARN] = 'arn:aws:secretsmanager:us-west-2:123456789012:secret:mysecret'
os.environ[ENV_ODS_DB_NAME] = 'mydatabase'
os.environ[ENV_ODS_OUTPUT_QUEUE_URL] = 'ENV_ODS_OUTPUT_QUEUE_URL'

from unittest.mock import patch
import json
from ods.ods_history_processor_lambda import lambda_handler

@patch('ods.ods_history_processor_lambda.transform_message')
@patch('ods.ods_history_processor_lambda.sqs_client')
@patch('ods.ods_history_processor_lambda.rds_data_client')
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