import unittest
from unittest.mock import patch
import os
import json
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['SINCH_AUTH_URL'] = 'SINCH_AUTH_URL'
os.environ['SINCH_CLIENT_CREDENTIAL_PATH'] = 'SINCH_CLIENT_CREDENTIAL_PATH'
from refresh_sinch_token.const import ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH
from refresh_sinch_token.handler import (
    generate_token,
    get_parameters_from_ssm,
    lambda_handler,
    store_token_in_ssm,
    validate_non_empty_string,
)


class TestHandler(unittest.TestCase):

    @patch('refresh_sinch_token.handler.SinchTokenService')
    def test_generate_token(self, mock_SinchTokenService):
        mock_instance = mock_SinchTokenService.return_value
        mock_instance.generate_token.return_value = 'token'
        assert generate_token('client_id', 'client_secret', 'auth_url') ==  'token'

    @patch('refresh_sinch_token.handler.ssm_service.put_ssm_parameter_with_env')
    def test_store_token_in_ssm(self, mock_put_ssm_parameter_with_env):
        store_token_in_ssm('code1', 'token', 'app_id', 'project_id', 'client_id', 'client_secret')
        ssm_value = json.dumps({
            'token': 'token',
            'app_id': 'app_id',
            'project_id': 'project_id',
            'client_id': 'client_id',
            'client_secret': 'client_secret'
        })
        mock_put_ssm_parameter_with_env.assert_called_once_with('code1', ssm_value)

    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.ssm_service.get_ssm_parameter_with_env')
    @patch('refresh_sinch_token.handler.generate_token')
    @patch('refresh_sinch_token.handler.store_token_in_ssm')
    def test_lambda_handler(self, mock_store_token_in_ssm, mock_generate_token, mock_get_ssm_parameter_with_env, mock_get_parameters_by_path):
        mock_generate_token.return_value = 'token'
        response = lambda_handler(None, None)
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], 'Successfully stored sms codes and tokens in SSM parameters.')

    @patch('refresh_sinch_token.handler.ssm_service')
    @patch('refresh_sinch_token.handler.logger')
    def test_get_parameters_from_ssm_success(self, mock_logger, mock_ssm_service):
        # Mock SSM service response
        mock_ssm_service.get_parameters_by_path.return_value = [{'Name': 'test', 'Value': 'value'}]

        # Call the function
        path = '/test/path'
        result = get_parameters_from_ssm(path)

        # Assert that the result matches the mocked response
        self.assertEqual(result, [{'Name': 'test', 'Value': 'value'}])
        mock_logger.info.assert_called_once_with("Successfully retrieved parameters from SSM: [{'Name': 'test', 'Value': 'value'}]")

    @patch('refresh_sinch_token.handler.ssm_service')
    @patch('refresh_sinch_token.handler.logger')
    def test_get_parameters_from_ssm_failure(self, mock_logger, mock_ssm_service):
        # Mock SSM service to raise an exception
        mock_ssm_service.get_parameters_by_path.side_effect = Exception("SSM error")

        # Call the function and check that it raises an exception
        with self.assertRaises(Exception) as context:
            get_parameters_from_ssm('/test/path')

        self.assertEqual(str(context.exception), "SSM error")
        mock_logger.exception.assert_called_once_with("Exception occurred while fetching parameters from SSM: SSM error")

    @patch('refresh_sinch_token.handler.SinchTokenService')
    @patch('refresh_sinch_token.handler.logger')
    def test_generate_token_success(self, mock_logger, mock_sinch_token_service):
        # Mock token service to return a token
        mock_sinch_token_service_instance = mock_sinch_token_service.return_value
        mock_sinch_token_service_instance.generate_token.return_value = "test_token"

        # Call the function
        token = generate_token('client_id', 'client_secret', 'auth_url')

        # Assert that the token is correct
        self.assertEqual(token, 'test_token')
        mock_logger.info.assert_called_once_with("Successfully generated token for client_id client_id")

    @patch('refresh_sinch_token.handler.SinchTokenService')
    @patch('refresh_sinch_token.handler.logger')
    def test_generate_token_failure(self, mock_logger, mock_sinch_token_service):
        # Mock token service to raise an exception
        mock_sinch_token_service_instance = mock_sinch_token_service.return_value
        exception_msg = "Token error"
        mock_sinch_token_service_instance.generate_token.side_effect = Exception(exception_msg)

        # Call the function and check that it raises an exception
        with self.assertRaises(Exception) as context:
            generate_token('client_id', 'client_secret', 'auth_url')

        self.assertEqual(str(context.exception), exception_msg)
        mock_logger.exception.assert_called_once_with(f"Failed to generate token for client_id client_id: {exception_msg}")

    @patch('refresh_sinch_token.handler.ssm_service')
    @patch('refresh_sinch_token.handler.logger')
    def test_store_token_in_ssm_success(self, mock_logger, mock_ssm_service):
        # Call the function
        store_token_in_ssm('sms_code', 'test_token', 'app_id', 'project_id', 'client_id', 'client_secret')

        # Assert that the SSM service was called with the correct parameters
        mock_ssm_service.put_ssm_parameter_with_env.assert_called_once_with(
            'sms_code',
            '{"token": "test_token", "app_id": "app_id", "project_id": "project_id", "client_id": "client_id", "client_secret": "client_secret"}'
        )
        mock_logger.info.assert_called_once_with("Successfully stored token for SMS code sms_code in SSM parameters.")

    @patch('refresh_sinch_token.handler.ssm_service')
    @patch('refresh_sinch_token.handler.logger')
    def test_store_token_in_ssm_failure(self, mock_logger, mock_ssm_service):
        # Mock SSM service to raise an exception
        mock_ssm_service.put_ssm_parameter_with_env.side_effect = Exception("SSM error")

        # Call the function and check that it raises an exception
        with self.assertRaises(Exception) as context:
            store_token_in_ssm('sms_code', 'test_token', 'app_id', 'project_id', 'client_id', 'client_secret')

        self.assertEqual(str(context.exception), "SSM error")
        mock_logger.exception.assert_called_once_with("Failed to store token for SMS code sms_code: SSM error")

    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.ssm_service.get_ssm_parameter_with_env')
    @patch('refresh_sinch_token.handler.get_parameters_from_ssm')
    @patch('refresh_sinch_token.handler.generate_token')
    @patch('refresh_sinch_token.handler.logger')
    def test_lambda_handler_failure(
        self,
        mock_logger,
        mock_generate_token,
        mock_get_parameters_from_ssm,
        mock_get_ssm_parameter_with_env,
        mock_get_parameters_by_path
    ):
        # Mock the SSM parameter and token generation with an exception
        mock_get_parameters_from_ssm.return_value = [{'Name': '/test/sms_code', 'Value': '{"app_id": "app_id", "project_id": "project_id", "client_id": "client_id", "client_secret": "client_secret"}'}]
        mock_generate_token.side_effect = Exception("Token generation failed")

        # Call the lambda handler and check for raised exception
        with self.assertRaises(Exception) as context:
            lambda_handler({}, {})

        self.assertIn("Some operations failed: ", str(context.exception))
        mock_logger.error.assert_called_with("Some operations failed: Token generation failed")
    
    def test_validate_non_empty_string(self):
        with self.assertRaises(ValueError):
            validate_non_empty_string('', 'TestValue')
        with self.assertRaises(ValueError):
            validate_non_empty_string('   ', 'TestValue')
        self.assertEqual(validate_non_empty_string('valid', 'TestValue'), 'valid')

    @patch('refresh_sinch_token.handler.ssm_service')
    @patch('refresh_sinch_token.handler.logger')
    def test_get_parameters_from_ssm_empty(self, mock_logger, mock_ssm_service):
        # Mock SSM service to return no parameters
        mock_ssm_service.get_parameters_by_path.return_value = []

        # Call the function and check for ValueError
        with self.assertRaises(ValueError) as context:
            get_parameters_from_ssm('/test/path')

        self.assertEqual(str(context.exception), "No parameters found at path: /test/path")
        mock_logger.error.assert_called_once_with("No parameters found at path: /test/path")

    @patch('refresh_sinch_token.handler.ssm_service.get_ssm_parameter_with_env')
    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.generate_token')
    @patch('refresh_sinch_token.handler.store_token_in_ssm')
    @patch('refresh_sinch_token.handler.logger')
    def test_lambda_handler_partial_failure(self, mock_logger, mock_store_token_in_ssm, mock_generate_token, mock_get_parameters_by_path, mock_get_ssm_parameter_with_env):
        # Mock parameters and partial failures
        mock_get_ssm_parameter_with_env.return_value = 'auth_url'
        mock_get_parameters_by_path.return_value = [
            {'Name': '/test/sms_code1', 'Value': json.dumps({
                'app_id': 'app_id1',
                'project_id': 'project_id1',
                'client_id': 'client_id1',
                'client_secret': 'client_secret1'
            })},
            {'Name': '/test/sms_code2', 'Value': json.dumps({
                'app_id': 'app_id2',
                'project_id': 'project_id2',
                'client_id': 'client_id2',
                'client_secret': 'client_secret2'
            })}
        ]
        # Simulate failure for the second token generation
        mock_generate_token.side_effect = ['token1', Exception('Token generation failed for client_id2')]

        with self.assertRaises(Exception) as context:
            lambda_handler({}, {})

        self.assertIn("Some operations failed", str(context.exception))
        mock_logger.error.assert_any_call("Some operations failed: Token generation failed for client_id2")

    @patch('refresh_sinch_token.handler.SinchTokenService')
    def test_generate_token_empty_token(self, mock_sinch_token_service):
        mock_sinch_token_service.return_value.generate_token.return_value = ''
        with self.assertRaises(ValueError) as context:
            generate_token('client_id', 'client_secret', 'auth_url')
        self.assertEqual(str(context.exception), "Generated token is empty for client_id client_id")

    @patch('refresh_sinch_token.handler.ssm_service')
    @patch('refresh_sinch_token.handler.logger')
    def test_store_token_in_ssm_missing_parameters(self, mock_logger, mock_ssm_service):
        # Test missing parameters for store_token_in_ssm
        with self.assertRaises(ValueError) as context:
            store_token_in_ssm('', 'token', 'app_id', 'project_id', 'client_id', 'client_secret')
        self.assertEqual(str(context.exception), "SMS Code must be a non-empty string")

        with self.assertRaises(ValueError) as context:
            store_token_in_ssm('sms_code', '', 'app_id', 'project_id', 'client_id', 'client_secret')
        self.assertEqual(str(context.exception), "Token must be a non-empty string")

    @patch('refresh_sinch_token.handler.ssm_service.get_ssm_parameter_with_env')
    def test_lambda_handler_missing_env_variable(self, mock_get_ssm_parameter_with_env):
        mock_get_ssm_parameter_with_env.side_effect = KeyError('ENV_LAMBDA_SINCH_AUTH_URL')

        with self.assertRaises(KeyError) as context:
            lambda_handler({}, {})
        
        self.assertEqual(str(context.exception), "'ENV_LAMBDA_SINCH_AUTH_URL'")
    
    @patch('refresh_sinch_token.handler.ssm_service.get_ssm_parameter_with_env')
    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.logger')
    def test_lambda_handler_missing_client_credential_path(self, mock_logger, mock_get_parameters_by_path, mock_get_ssm_parameter_with_env):
        # Simulate missing client credential path in environment
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                lambda_handler({}, {})

        self.assertIn(f"Environment variable {ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH} is required.", str(context.exception))
        mock_logger.error.assert_called_once_with("Client credential path environment variable is not set.")

    @patch('refresh_sinch_token.handler.ssm_service.get_ssm_parameter_with_env')
    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.logger')
    def test_lambda_handler_invalid_json_in_ssm(self, mock_logger, mock_get_parameters_by_path, mock_get_ssm_parameter_with_env):
        # Mock invalid JSON in SSM response
        mock_get_parameters_by_path.return_value = [{'Name': '/test/sms_code', 'Value': '{invalid_json}'}]

        with self.assertRaises(Exception):
            lambda_handler({}, {})

        mock_logger.exception.assert_called_once_with("Operation failed for short code sms_code: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)")

    # Test invalid input types for store_token_in_ssm
    def test_store_token_in_ssm_invalid_types(self):
        with self.assertRaises(ValueError) as context:
            store_token_in_ssm(None, 'token', 'app_id', 'project_id', 'client_id', 'client_secret')
        self.assertEqual(str(context.exception), "SMS Code must be a non-empty string")

        with self.assertRaises(ValueError) as context:
            store_token_in_ssm('sms_code', None, 'app_id', 'project_id', 'client_id', 'client_secret')
        self.assertEqual(str(context.exception), "Token must be a non-empty string")

    # Test unexpected input types for generate_token
    def test_generate_token_invalid_types(self):
        with self.assertRaises(ValueError) as context:
            generate_token(123, 'client_secret', 'auth_url')
        self.assertEqual(str(context.exception), "Client ID must be a non-empty string")

        with self.assertRaises(ValueError) as context:
            generate_token('client_id', None, 'auth_url')
        self.assertEqual(str(context.exception), "Client Secret must be a non-empty string")

    # Test when get_parameters_from_ssm returns empty list
    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.logger')
    def test_get_parameters_from_ssm_empty_response(self, mock_logger, mock_get_parameters_by_path):
        # Mock no parameters in SSM response
        mock_get_parameters_by_path.return_value = []

        with self.assertRaises(ValueError) as context:
            get_parameters_from_ssm('/test/path')

        self.assertEqual(str(context.exception), "No parameters found at path: /test/path")
        mock_logger.error.assert_called_once_with("No parameters found at path: /test/path")

    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.logger')
    def test_get_parameters_from_ssm_invalid_response(self, mock_logger, mock_get_parameters_by_path):
        # Mock invalid response from SSM
        mock_get_parameters_by_path.return_value = None

        with self.assertRaises(ValueError):
            get_parameters_from_ssm('/test/path')

        mock_logger.exception.assert_called_once_with("Exception occurred while fetching parameters from SSM: No parameters found at path: /test/path")

    # Test lambda_handler when all operations fail
    @patch('refresh_sinch_token.handler.generate_token')
    @patch('refresh_sinch_token.handler.ssm_service.get_ssm_parameter_with_env')
    @patch('refresh_sinch_token.handler.ssm_service.get_parameters_by_path')
    @patch('refresh_sinch_token.handler.store_token_in_ssm')
    @patch('refresh_sinch_token.handler.logger')
    def test_lambda_handler_all_operations_fail(self, mock_logger, mock_store_token_in_ssm, mock_get_parameters_by_path, mock_get_ssm_parameter_with_env, mock_generate_token):
        # Mock successful SSM fetch but failed token generation and storage
        mock_get_ssm_parameter_with_env.return_value = 'auth_url'
        mock_get_parameters_by_path.return_value = [
            {'Name': '/test/sms_code1', 'Value': json.dumps({
                'app_id': 'app_id1',
                'project_id': 'project_id1',
                'client_id': 'client_id1',
                'client_secret': 'client_secret1'
            })}
        ]
        mock_generate_token.side_effect = Exception("Token generation failed")
        mock_store_token_in_ssm.side_effect = Exception("SSM storage failed")

        with self.assertRaises(Exception) as context:
            lambda_handler({}, {})

        self.assertIn("Some operations failed", str(context.exception))
        mock_logger.error.assert_called_with("Some operations failed: Token generation failed")
    

if __name__ == '__main__':
    unittest.main()