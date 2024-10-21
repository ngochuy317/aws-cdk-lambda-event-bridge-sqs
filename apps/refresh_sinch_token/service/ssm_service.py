import os
import boto3

# pylint: disable=too-few-public-methods
class SSMService:
    def __init__(self, env, logger):
        self.env = env
        self.ssm_client = boto3.client('ssm')
        self.logger = logger

    def get_ssm_parameter_with_env(self, parameter_name, with_decryption=True):
        parameter_with_env = f'/{self.env}{os.environ[parameter_name]}'

        response = self.ssm_client.get_parameter(Name=parameter_with_env, WithDecryption=with_decryption)

        if response:
            return response['Parameter']['Value']

        self.logger.error("Parameter %s doesn't exist in SSM", parameter_with_env)
        return None
        
    def get_parameters_by_path(self, path):
        try:
            response = self.ssm_client.get_parameters_by_path(
                Path=path,
                Recursive=True,
                WithDecryption=True
            )
            return response['Parameters']
        except Exception as e:
            self.logger.error(f"Failed to get parameters by path {path}: {e}")
            raise
    
    def put_ssm_parameter_with_env(self, parameter_value, token):
        try:
            self.ssm_client.put_parameter(
                Name=parameter_value,
                Value=token,
                Type='SecureString',
                Overwrite=True
            )
            self.logger.info(f"Successfully put parameter {parameter_value} in SSM")
        except self.ssm_client.exceptions.ParameterAlreadyExists:
            self.logger.error(f"Parameter {parameter_value} already exists in SSM")
        except self.ssm_client.exceptions.ParameterLimitExceeded:
            self.logger.error(f"Parameter limit exceeded for {parameter_value}")
        except self.ssm_client.exceptions.TooManyUpdates:
            self.logger.error(f"Too many updates for {parameter_value}")
        except Exception as e:
            self.logger.error(f"Failed to put parameter {parameter_value} in SSM: {e}")
            raise
