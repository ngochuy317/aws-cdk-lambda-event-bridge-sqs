import boto3


# pylint: disable=too-few-public-methods
class SSMService:
    def __init__(self, logger, env):
        self.logger = logger
        self.env = env
        self.ssm_client = boto3.client('ssm')

    def get_ssm_parameter_with_env(self, parameter_name, with_decryption=True):
        parameter_with_env = f'/{self.env}{parameter_name}'

        self.logger.info("Going to read parameter %s from SSM", parameter_with_env)
        response = self.ssm_client.get_parameter(Name=parameter_with_env, WithDecryption=with_decryption)

        if response:
            self.logger.info("Successfully read parameter %s", parameter_with_env)
            self.logger.debug("Value from SSM %s", response['Parameter']['Value'])
            return response['Parameter']['Value']

        self.logger.warning("Parameter %s doesn't exist in SSM", parameter_with_env)
        return None
