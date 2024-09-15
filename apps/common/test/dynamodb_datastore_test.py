from unittest.mock import Mock, patch
import logging
import pytest
import botocore.exceptions
from common.dynamodb_datastore import DynamoDbDatastore


@pytest.fixture(scope='function')
@patch('common.dynamodb_datastore.boto3')
def test_service(boto3_mock):
    dynamo_mock = Mock()
    table_mock = Mock()

    dynamo_mock.Table.return_value = table_mock
    boto3_mock.resource.return_value = dynamo_mock

    return DynamoDbDatastore('test-table', logging.getLogger('DynamoDBTest'))


@pytest.fixture(scope='function')
@patch('common.dynamodb_datastore.boto3')
def test_arn_service(boto3_mock):
    dynamo_mock = Mock()
    sts_mock = Mock()
    table_mock = Mock()

    dynamo_mock.Table.return_value = table_mock
    boto3_mock.resource.return_value = dynamo_mock
    boto3_mock.client.return_value = sts_mock

    sts_mock.assume_role.return_value = {
        'Credentials': {
            'AccessKeyId': 'test-key',
            'SecretAccessKey': 'test-secret',
            'SessionToken': 'test-token'
        }
    }

    return DynamoDbDatastore('test-table', logging.getLogger('DynamoDBTest'), 'TestArn')


def test_create_select_projection_none_fields(test_service):
    projection_expr, expression_names = test_service.create_select_projection(None)

    assert projection_expr is None
    assert expression_names is None


def test_create_select_projection_non_empty_fields(test_service):
    projection_expr, expression_names = test_service.create_select_projection(['test-field', 'test-field-2'])

    assert projection_expr == '#test-field,#test-field-2'
    assert expression_names == {'#test-field': 'test-field', '#test-field-2': 'test-field-2'}


def test_get_item_non_empty_fields(test_service):
    test_service.get_item({'test': 'test'}, ['field'])
    test_service.table.get_item.assert_called_once_with(
        Key={'test': 'test'}, ProjectionExpression='#field', ExpressionAttributeNames={'#field': 'field'}
    )


def test_get_item_empty_fields(test_service):
    test_service.get_item({'test': 'test'})
    test_service.table.get_item.assert_called_once_with(Key={'test': 'test'})


def test_call_with_cross_acc_no_error(test_service):
    def test_call():
        return True

    response = test_service.call_with_cross_acc(test_call)
    assert response


def test_call_with_cross_acc_no_arn_with_error(test_service):
    def test_call():
        raise botocore.exceptions.ClientError(error_response={
            'Error': {
                'Code': 'TestError',
                'Message': 'Test error message'
            }
        }, operation_name='test_call')

    with pytest.raises(botocore.exceptions.ClientError) as e_info:
        response = test_service.call_with_cross_acc(test_call)


def test_call_with_cross_acc_with_arn_with_wrong_error(test_service):
    num_calls = {
        'calls': 0
    }

    def test_call(local_num_calls):
        if local_num_calls['calls'] == 0:
            local_num_calls['calls'] = local_num_calls['calls'] + 1
            raise botocore.exceptions.ClientError(error_response={
                'Error': {
                    'Code': 'TestError',
                    'Message': 'Test error message'
                }
            }, operation_name='test_call')

        return True

    with pytest.raises(botocore.exceptions.ClientError) as e_info:
        response = test_service.call_with_cross_acc(lambda: test_call(num_calls))


@patch('common.dynamodb_datastore.boto3')
def test_call_with_cross_acc_with_arn_with_expired_error(boto3_mock, test_arn_service):
    num_calls = {
        'calls': 0
    }
    sts_mock = Mock()

    boto3_mock.client.return_value = sts_mock

    sts_mock.assume_role.return_value = {
        'Credentials': {
            'AccessKeyId': 'test-key',
            'SecretAccessKey': 'test-secret',
            'SessionToken': 'test-token'
        }
    }

    def test_call(local_num_calls):
        if local_num_calls['calls'] == 0:
            local_num_calls['calls'] = local_num_calls['calls'] + 1
            raise botocore.exceptions.ClientError(error_response={
                'Error': {
                    'Code': 'ExpiredTokenException',
                    'Message': 'Test error message'
                }
            }, operation_name='test_call')

        return True

    response = test_arn_service.call_with_cross_acc(lambda: test_call(num_calls))
    sts_mock.assume_role.assert_called()
    assert response
