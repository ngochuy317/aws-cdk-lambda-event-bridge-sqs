import os

import boto3
import moto
import pytest

# from collect_data.common.ssm_service import SSMService

@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# def test_ssm_read(aws_credentials):
#     os.environ['GLOBAL_ENVIRONMENT'] = 'dev'
#     os.environ['QWE'] = '/qwe/param'
#     with moto.mock_ssm():
#         ssm_client = boto3.client('ssm')
#         ssm_client.put_parameter(Name='/dev/qwe/param', Value='value-qwe', Overwrite=True, Type='SecureString')
#         client = SSMService()

#         res = client.get_ssm_parameter_with_env('QWE')
#         assert res == 'value-qwe'