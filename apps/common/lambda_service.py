import json
import boto3


class LambdaInvocationException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)


class LambdaService:
    def __init__(self, logger):
        self.logger = logger
        self.lambda_client = boto3.client('lambda')

    def invoke_function(self, function_name, payload=''):
        self.logger.info('Calling %s AWS Lambda with payload %s', function_name, payload)
        response = self.lambda_client.invoke(
            FunctionName=function_name,
            Payload=payload
        )

        if 'FunctionError' in response:
            raise LambdaInvocationException(response['Payload'].read())

        return {
            'status': response['StatusCode'],
            'payload': json.loads(response['Payload'].read().decode('utf-8'))
        }
