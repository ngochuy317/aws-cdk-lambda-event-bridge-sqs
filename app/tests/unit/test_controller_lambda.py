import os
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

import json
from unittest.mock import patch
from datetime import datetime
from app.cdk.aws_lambda import controller_lambda


@patch('app.cdk.aws_lambda.controller_lambda.sqs')
def test_enable_queue(mock_sqs):
    mock_queue_url = "https://sqs.region.amazonaws.com/123456789012/MyQueue"
    controller_lambda.enable_queue(mock_queue_url)
    expected_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "SQS:SendMessage",
                "Resource": mock_queue_url
            }
        ]
    }
    mock_sqs.set_queue_attributes.assert_called_with(
        QueueUrl=mock_queue_url,
        Attributes={
            'Policy': json.dumps(expected_policy)
        }
    )


@patch('app.cdk.aws_lambda.controller_lambda.sqs')
def test_disable_queue(mock_sqs):
    mock_queue_url = "https://sqs.region.amazonaws.com/123456789012/MyQueue"
    controller_lambda.disable_queue(mock_queue_url)
    mock_sqs.set_queue_attributes.assert_called_with(
        QueueUrl=mock_queue_url,
        Attributes={
            'Policy': ''
        }
    )


def test_get_current_timezone():
    assert controller_lambda.get_current_timezone("MyQueuePST") == "America/Los_Angeles"
    assert controller_lambda.get_current_timezone("MyQueue.fifoPST") == "America/Los_Angeles"
    assert controller_lambda.get_current_timezone("MyQueueCST") == "America/Chicago"
    assert controller_lambda.get_current_timezone("MyQueueXYZ") == "America/New_York"


@patch('app.cdk.aws_lambda.controller_lambda.pytz.timezone')
@patch('app.cdk.aws_lambda.controller_lambda.datetime')
def test_get_current_time(mock_datetime, mock_pytz_timezone):
    mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0, 0)
    mock_pytz_timezone.return_value = "America/Los_Angeles"
    assert controller_lambda.get_current_time("America/Los_Angeles") == datetime(2023, 1, 1, 12, 0, 0)


def test_is_within_eligibility_window():
    current_time = datetime(2023, 1, 1, 12, 0, 0)
    assert controller_lambda.is_within_eligibility_window(current_time)

    current_time = datetime(2023, 1, 1, 22, 0, 0)
    assert not controller_lambda.is_within_eligibility_window(current_time)


@patch('app.cdk.aws_lambda.controller_lambda.get_current_time')
@patch('app.cdk.aws_lambda.controller_lambda.get_current_timezone')
@patch('app.cdk.aws_lambda.controller_lambda.sqs')
@patch('app.cdk.aws_lambda.controller_lambda.disable_queue')
def test_lambda_handler_disable_queue_out_of_eligibility_window(
    mock_disable_queue,
    mock_sqs,
    mock_get_current_timezone,
    mock_get_current_time
):
    mock_event = {}
    mock_context = {}

    mock_get_current_timezone.return_value = "America/Los_Angeles"
    mock_get_current_time.return_value = datetime(2023, 1, 1, 22, 0, 0)

    mock_sqs.get_queue_attributes.return_value = {'Attributes': {'Policy': '{"Effect": "Allow"}'}}

    with patch.dict('os.environ', {
        'QUEUE_NAMES': 'MyQueue',
        'REGION': 'region',
        'ACCOUNT_ID': '123456789012'
    }):
        response = controller_lambda.lambda_handler(mock_event, mock_context)
        assert response['statusCode'] == 200
        assert response['body'] == 'Queue statuses updated successfully.'
        assert mock_disable_queue.called is True


@patch('app.cdk.aws_lambda.controller_lambda.get_current_time')
@patch('app.cdk.aws_lambda.controller_lambda.get_current_timezone')
@patch('app.cdk.aws_lambda.controller_lambda.sqs')
@patch('app.cdk.aws_lambda.controller_lambda.enable_queue')
def test_lambda_handler_enable_queue_within_eligibility_window(
    mock_enable_queue,
    mock_sqs,
    mock_get_current_timezone,
    mock_get_current_time
):
    mock_event = {}
    mock_context = {}

    mock_get_current_timezone.return_value = "America/Los_Angeles"
    mock_get_current_time.return_value = datetime(2023, 1, 1, 10, 0, 0)

    mock_sqs.get_queue_attributes.return_value = {'Attributes': {'Policy': ''}}

    with patch.dict('os.environ', {
        'QUEUE_NAMES': 'MyQueue',
        'REGION': 'region',
        'ACCOUNT_ID': '123456789012'
    }):
        response = controller_lambda.lambda_handler(mock_event, mock_context)
        assert response['statusCode'] == 200
        assert response['body'] == 'Queue statuses updated successfully.'
        assert mock_enable_queue.called is True


@patch('app.cdk.aws_lambda.controller_lambda.get_current_time')
@patch('app.cdk.aws_lambda.controller_lambda.get_current_timezone')
@patch('app.cdk.aws_lambda.controller_lambda.sqs')
@patch('app.cdk.aws_lambda.controller_lambda.enable_queue')
@patch('app.cdk.aws_lambda.controller_lambda.disable_queue')
def test_lambda_handler_do_nothing_within_eligibility_window(
    mock_disable_queue,
    mock_enable_queue,
    mock_sqs,
    mock_get_current_timezone,
    mock_get_current_time
):
    mock_event = {}
    mock_context = {}

    mock_get_current_timezone.return_value = "America/Los_Angeles"
    mock_get_current_time.return_value = datetime(2023, 1, 1, 10, 0, 0)

    mock_sqs.get_queue_attributes.return_value = {'Attributes': {'Policy': '{"Effect": "Allow"}'}}

    with patch.dict('os.environ', {
        'QUEUE_NAMES': 'MyQueue',
        'REGION': 'region',
        'ACCOUNT_ID': '123456789012'
    }):
        response = controller_lambda.lambda_handler(mock_event, mock_context)
        assert response['statusCode'] == 200
        assert response['body'] == 'Queue statuses updated successfully.'
        assert mock_enable_queue.called is False
        assert mock_disable_queue.called is False
