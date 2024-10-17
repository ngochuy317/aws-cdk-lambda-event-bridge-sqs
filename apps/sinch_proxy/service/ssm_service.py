import os
import boto3

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
                Path=f'/{self.env}{path}',
                Recursive=True,
                WithDecryption=True
            )
            return response['Parameters']
        except Exception as e:
            self.logger.error(f"Failed to get parameters by path {path}: {e}")
            raise