import boto3
import os


class SsmClient:
    def __init__(self):
        self.env = os.environ['GLOBAL_ENVIRONMENT']
        self.ssm_client = boto3.client('ssm')

    def get_ssm_parameter(self, name):
        key_name = f'/{self.env}{name}'
        print(f"Retrieving {key_name} from SSM!")
        response = self.ssm_client.get_parameter(Name=key_name, WithDecryption=True)

        return response['Parameter']['Value']

    def get_ssm_env_parameter(self, env_name):
        return self.get_ssm_parameter(os.environ.get(env_name))
