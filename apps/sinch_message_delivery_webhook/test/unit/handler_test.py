import pytest, os, json, sys

# Set the environment variables required by main.py
os.environ['REQUEST_LOG_TABLE'] = 'dummy_value'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'  # Set your desired AWS region

from sinch_message_delivery_webhook.main import check_bot_entries

def test_check_bot_entries_positive():
    event = {
        'message_delivery_report': {
            'metadata': json.dumps({
                'chl_bot_id': 'US-lsasli81',
                'chl_bot_version': 'DRAFT'
            })
        }
    }
    assert check_bot_entries(event) == True

def test_check_bot_entries_negative_no_metadata():
    event = {
        'message_delivery_report': {}
    }
    assert check_bot_entries(event) == False

def test_check_bot_entries_negative_no_bot_id():
    event = {
        'message_delivery_report': {
            'metadata': json.dumps({
                'chl_bot_version': 'DRAFT'
            })
        }
    }
    assert check_bot_entries(event) == False

def test_check_bot_entries_negative_no_bot_version():
    event = {
        'message_delivery_report': {
            'metadata': json.dumps({
                'chl_bot_id': 'US-lsasli81'
            })
        }
    }
    assert check_bot_entries(event) == False