from unittest.mock import Mock
import pytest
from common.dynamo_lock_service import dynamo_lock, DynamoLockException


dynamo_lock_service = Mock()


def get_lock_key(event):
    return event['lock_key']


@dynamo_lock(unique_request_id_func=get_lock_key, stage='test', lock_service=dynamo_lock_service)
def execute_test_method(event, context):
    if 'error' in event:
        raise ValueError()


@dynamo_lock(unique_request_id_func=get_lock_key, stage='test', lock_service=dynamo_lock_service)
def execute_test_method_extract(event, context):
    if 'error' in event:
        raise ValueError()


def test_handle_events_when_not_locked_and_func_successful_then_acquire_and_release_lock():
    event = {
        'lock_key': "lock_key"
    }

    dynamo_lock_service.reset_mock()
    dynamo_lock_service.acquire_lock.return_value = True
    execute_test_method(event, {})

    dynamo_lock_service.acquire_lock.assert_called_once()
    dynamo_lock_service.release_lock.assert_called_once()


def test_handle_events_when_locked_then_raise_lock_exception():
    event = {
        'lock_key': "lock_key"
    }

    dynamo_lock_service.reset_mock()
    dynamo_lock_service.acquire_lock.return_value = False

    with pytest.raises(DynamoLockException) as excinfo:
        execute_test_method(event, {})

    dynamo_lock_service.acquire_lock.assert_called_once()
    dynamo_lock_service.release_lock.assert_not_called()


def test_handle_events_when_not_locked_and_func_raised_exception_then_acquire_and_release_lock_and_propagate_exception():
    event = {
        'lock_key': "lock_key",
        'error': True
    }

    dynamo_lock_service.reset_mock()
    dynamo_lock_service.acquire_lock.return_value = True

    with pytest.raises(ValueError) as excinfo:
        execute_test_method(event, {})

    dynamo_lock_service.acquire_lock.assert_called_once()
    dynamo_lock_service.release_lock.assert_called_once()
