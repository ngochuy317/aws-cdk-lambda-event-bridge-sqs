import os
os.environ['STRATEGY_TABLE_NAME'] = 'mock_table_name'

import json
import pytest
from unittest.mock import patch, MagicMock
from http import HTTPStatus
import boto3
from botocore.exceptions import NoRegionError

# Set up the region for boto3
boto3.setup_default_session(region_name='us-east-2')

from mulesoft_proxy.handler import (
    lambda_handler,
    enrich_customer_account_with_strategy,
    get_proxy_handlers,
    handle_check_outreach_count,
    extract_params,
    handle_get_customer_account,
    handle_update_customer_account,
    handle_update_popup,
    handle_get_customer_account_with_strategy_table,
    replace_phone_number_in_url
)
from mulesoft_proxy.const import (
    ENV_LAMBDA_MULESOFT_CLIENT_ID,
    ENV_LAMBDA_MULESOFT_CLIENT_SECRET,
    ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT,
    ENV_STRATEGY_TABLE_NAME,
    ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT,
    ENV_LAMBDA_MULESOFT_USERNAME,
    ENV_LAMBDA_MULESOFT_PASSWORD,
    ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT,
)
from apps.common.constants import get_logger, get_global_environment

# Mock logger
logger_patch = patch('mulesoft_proxy.handler.logger')
logger_mock = logger_patch.start()

# Mock create_mulesoft_service
create_mulesoft_service_patch = patch('mulesoft_proxy.handler.create_mulesoft_service')
create_mulesoft_service_mock = create_mulesoft_service_patch.start()

# Mock call_url_based_on_proxy_name
call_url_based_on_proxy_name_patch = patch('mulesoft_proxy.handler.call_url_based_on_proxy_name')
call_url_based_on_proxy_name_mock = call_url_based_on_proxy_name_patch.start()

# Mock environment variables
@pytest.fixture(autouse=True)
def mock_env_vars():
    with patch.dict(os.environ, {
        ENV_STRATEGY_TABLE_NAME: 'mock_table_name',
        ENV_LAMBDA_MULESOFT_CLIENT_ID: 'mock_client_id',
        ENV_LAMBDA_MULESOFT_CLIENT_SECRET: 'mock_client_secret',
        ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT: 'mock_customer_account_endpoint',
        ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT: 'mock_outreach_endpoint',
        ENV_LAMBDA_MULESOFT_USERNAME: 'mock_username',
        ENV_LAMBDA_MULESOFT_PASSWORD: 'mock_password',
        ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT: 'mock_popup_endpoint'
    }):
        yield

# Mock dynamodb.Table
@pytest.fixture
def mock_dynamodb_table():
    with patch('boto3.resource') as mock_dynamodb_resource:
        mock_table = MagicMock()
        mock_dynamodb_resource.return_value.Table.return_value = mock_table
        yield mock_table

def test_lambda_handler(mock_dynamodb_table):
    # Your test logic here
    event = {}  # Define your event
    context = {}  # Define your context
    response = lambda_handler(event, context)
    # Add assertions to validate the response
    assert response is not None

# Ensure patches are stopped after tests
@pytest.fixture(scope="module", autouse=True)
def stop_patches():
    yield
    logger_patch.stop()
    create_mulesoft_service_patch.stop()
    call_url_based_on_proxy_name_patch.stop()

@pytest.fixture
def event():
    return {
        'body': json.dumps({'proxy_name': 'test_proxy'})
    }

@pytest.fixture
def context():
    return {}

# Sample customer account data
sample_customer_account = {
    'body': json.dumps([
        {'score_account_id': '12345'},
        {'score_account_id': '67890'},
        {'score_account_id': None}
    ]).encode('utf-8')
}

# Mock response from DynamoDB table
mock_response = {
    'Item': {
        'PRODUCT': 'ProductA',
        'SITE': 'SiteA',
        'BOM_DQ': 'DQ123',
        'PRD_END_DATE': '2023-12-31'
    }
}

@patch('mulesoft_proxy.handler.table.get_item')
def test_enrich_customer_account_with_strategy_success(mock_get_item):
    # Setup mock
    mock_get_item.return_value = mock_response

    # Call the function
    result = enrich_customer_account_with_strategy(sample_customer_account)

    # Decode and parse the result body
    result_body = json.loads(result['body'].decode('utf-8'))

    # Assertions
    assert len(result_body) == 3
    assert result_body[0]['product'] == 'ProductA'
    assert result_body[0]['site'] == 'SiteA'
    assert result_body[0]['bom_dq'] == 'DQ123'
    assert result_body[0]['strategy_month_end_date'] == '2023-12-31'
    assert result_body[2]['product'] == '' 

@patch('mulesoft_proxy.handler.table.get_item')
def test_enrich_customer_account_with_strategy_missing_score_account_id(mock_get_item):
    # Setup mock
    mock_get_item.return_value = mock_response

    # Modify sample data to have a record without score_account_id
    customer_account = {
        'body': json.dumps([
            {'score_account_id': None}
        ]).encode('utf-8')
    }

    # Call the function
    result = enrich_customer_account_with_strategy(customer_account)

    # Decode and parse the result body
    result_body = json.loads(result['body'].decode('utf-8'))

    # Assertions
    assert len(result_body) == 1
    assert 'product' in result_body[0] 

@patch('mulesoft_proxy.handler.table.get_item')
def test_enrich_customer_account_with_strategy_exception(mock_get_item):
    # Setup mock to raise an exception
    mock_get_item.side_effect = Exception("DynamoDB error")

    # Call the function
    result = enrich_customer_account_with_strategy(sample_customer_account)

    # Decode and parse the result body
    result_body = json.loads(result['body'].decode('utf-8'))

    # Assertions
    assert len(result_body) == 3
    assert result_body[0]['product'] == ''  # Product should be an empty value due to exception
    assert result_body[2]['product'] == ''  # Product should be an empty value for missing score_account_id

@patch('mulesoft_proxy.handler.logger')
def test_get_proxy_handlers(mock_logger):
    # Call the function
    proxy_handlers = get_proxy_handlers()

    # Verify the debug log was called
    mock_logger.debug.assert_called_once_with("Getting proxy handlers")

    # Verify the info log was called with the correct message
    expected_handlers = {
        "get_customer_outreach": handle_check_outreach_count,
        "get_customer_account_branch_info": handle_get_customer_account,
        "update_customer_outreach": handle_update_customer_account,
        "update_popup": handle_update_popup,
        "get_customer_account_branch_info_with_strategy_data": handle_get_customer_account_with_strategy_table
    }
    mock_logger.info.assert_called_once_with(f"Proxy handlers: {expected_handlers}")

    # Verify the returned dictionary
    assert proxy_handlers == expected_handlers

@patch('mulesoft_proxy.handler.logger')
def test_extract_params_positive(mock_logger):
    # Positive test case with valid event_body_json
    event_body_json = {
        "proxy_metadata": {
            "param1": "value1",
            "param2": "value2"
        }
    }
    expected_params = {
        "param1": "value1",
        "param2": "value2"
    }

    # Call the function
    params = extract_params(event_body_json)

    # Verify the info log was called
    mock_logger.info.assert_any_call("Extracting parameters from event_body_json")
    mock_logger.info.assert_any_call(f"Extracted parameters: {expected_params}")

    # Verify the returned dictionary
    assert params == expected_params

@patch('mulesoft_proxy.handler.logger')
def test_extract_params_no_proxy_metadata(mock_logger):
    # Negative test case with no proxy_metadata in event_body_json
    event_body_json = {}
    expected_params = {}

    # Call the function
    params = extract_params(event_body_json)

    # Verify the returned dictionary
    assert params == expected_params

@patch('mulesoft_proxy.handler.logger')
def test_extract_params_empty_proxy_metadata(mock_logger):
    # Negative test case with empty proxy_metadata in event_body_json
    event_body_json = {
        "proxy_metadata": {}
    }
    expected_params = {}

    # Call the function
    params = extract_params(event_body_json)

    # Verify the info log was called
    mock_logger.info.assert_any_call("Extracting parameters from event_body_json")
    mock_logger.info.assert_any_call(f"Extracted parameters: {expected_params}")

    # Verify the returned dictionary
    assert params == expected_params


@patch('mulesoft_proxy.handler.logger')
def test_replace_phone_number_in_url_positive(mock_logger):
    # Positive test case with valid URL and event_body_json
    url = "https://example.com/user/{phone_number}/details"
    event_body_json = {
        "proxy_metadata": {
            "phone_number": "1234567890"
        }
    }
    expected_url = "https://example.com/user/1234567890/details"

    # Call the function
    result_url = replace_phone_number_in_url(url, event_body_json)

    # Verify the returned URL
    assert result_url == expected_url

@patch('mulesoft_proxy.handler.logger')
def test_replace_phone_number_in_url_no_phone_number(mock_logger):
    # Negative test case with no phone_number in event_body_json
    url = "https://example.com/user/{phone_number}/details"
    event_body_json = {
        "proxy_metadata": {}
    }

    # Call the function and expect a ValueError
    with pytest.raises(ValueError):
        replace_phone_number_in_url(url, event_body_json)


@patch('mulesoft_proxy.handler.logger')
def test_replace_phone_number_in_url_no_proxy_metadata(mock_logger):
    # Negative test case with no proxy_metadata in event_body_json
    url = "https://example.com/user/{phone_number}/details"
    event_body_json = {}

    # Call the function and expect a ValueError
    with pytest.raises(ValueError):
        replace_phone_number_in_url(url, event_body_json)


if __name__ == "__main__":
    pytest.main()