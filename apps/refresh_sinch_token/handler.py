import os
import json
from refresh_sinch_token.service.sinch_service import SinchTokenService
from refresh_sinch_token.service.ssm_service import SSMService
from refresh_sinch_token.const import (
    ENV_LAMBDA_SINCH_AUTH_URL,
    ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH,
    get_global_environment,
    get_logger,
)


logger = get_logger()
ssm_service = SSMService(get_global_environment(), logger)


def validate_non_empty_string(value, name):
    if not isinstance(value, str) or not value.strip():
        logger.error(f"Invalid {name}: Expected a non-empty string, got {value}")
        raise ValueError(f"{name} must be a non-empty string")
    return value


def get_parameters_from_ssm(path):
    validate_non_empty_string(path, "SSM path")
    try:
        parameters = ssm_service.get_parameters_by_path(path)
        if not parameters:
            logger.error(f"No parameters found at path: {path}")
            raise ValueError(f"No parameters found at path: {path}")
        logger.info(f"Successfully retrieved parameters from SSM: {parameters}")
        return parameters
    except Exception as e:
        logger.exception(f"Exception occurred while fetching parameters from SSM: {e}")
        raise


def generate_token(client_id, client_secret, auth_url):
    validate_non_empty_string(client_id, "Client ID")
    validate_non_empty_string(client_secret, "Client Secret")
    validate_non_empty_string(auth_url, "Auth URL")
    try:
        sinch_token_service = SinchTokenService(
            client_id=client_id,
            client_secret=client_secret,
            auth_url=auth_url,
            logger=logger
        )
        token = sinch_token_service.generate_token()
        if not token:
            logger.error(f"Token generation failed: Empty token for client_id {client_id}")
            raise ValueError(f"Generated token is empty for client_id {client_id}")
        
        logger.info(f"Successfully generated token for client_id {client_id}")
        return token
    except Exception as e:
        logger.exception(f"Failed to generate token for client_id {client_id}: {e}")
        raise


def store_token_in_ssm(sms_code, token, app_id, project_id, client_id, client_secret):
    """ Store token in SSM with validation and exception handling. """
    validate_non_empty_string(sms_code, "SMS Code")
    validate_non_empty_string(token, "Token")
    validate_non_empty_string(app_id, "App ID")
    validate_non_empty_string(project_id, "Project ID")
    validate_non_empty_string(client_id, "Client ID")
    validate_non_empty_string(client_secret, "Client Secret")

    try:
        ssm_value = json.dumps({
            'token': token,
            'app_id': app_id,
            'project_id': project_id,
            'client_id': client_id,
            'client_secret': client_secret
        })
        ssm_service.put_ssm_parameter_with_env(sms_code, ssm_value)
        logger.info(f"Successfully stored token for SMS code {sms_code} in SSM parameters.")
    except Exception as e:
        logger.exception(f"Failed to store token for SMS code {sms_code}: {e}")
        raise


def lambda_handler(event, context):
    failure_messages = []
    
    try:
        auth_url = ssm_service.get_ssm_parameter_with_env(ENV_LAMBDA_SINCH_AUTH_URL)
        if not auth_url:
            logger.error("Auth URL is not set in SSM or is empty.")
            raise ValueError("Auth URL cannot be empty.")
    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        raise

    try:
        client_credential_path = os.environ.get(ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH)
        if not client_credential_path:
            logger.error("Client credential path environment variable is not set.")
            raise ValueError(f"Environment variable {ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH} is required.")
        
        parameters = get_parameters_from_ssm(f'/{get_global_environment()}{client_credential_path}')
    except Exception as e:
        logger.exception(f"Error fetching parameters: {e}")
        raise

    for parameter in parameters:
        try:
            parameter_path = parameter['Name']
            sms_code = parameter_path.rsplit('/', 1)[-1]
            parameter_value = json.loads(parameter['Value'])
            app_id = parameter_value.get('app_id')
            project_id = parameter_value.get('project_id')
            client_id = parameter_value.get('client_id')
            client_secret = parameter_value.get('client_secret')

            if not all([app_id, project_id, client_id, client_secret]):
                logger.error(f"Missing required fields in parameters for SMS code {sms_code}")
                raise ValueError(f"Missing required fields for SMS code {sms_code}")

            token = generate_token(client_id, client_secret, auth_url)
            store_token_in_ssm(parameter_path, token, app_id, project_id, client_id, client_secret)
        
        except Exception as e:
            failure_messages.append(str(e))
            logger.exception(f"Operation failed for short code {sms_code}: {e}")
    
    if failure_messages:
        error_message = 'Some operations failed: ' + ', '.join(failure_messages)
        logger.error(error_message)
        raise Exception(error_message)

    logger.info("All tokens successfully stored in SSM parameters.")
    return {
        'statusCode': 200,
        'body': 'Successfully stored sms codes and tokens in SSM parameters.'
    }