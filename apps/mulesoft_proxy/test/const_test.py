import pytest
import os
import logging
from unittest.mock import patch
from apps.common.constants import (
    get_global_environment,
    is_non_prod,
    get_region,
    get_logger,
    ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY,
    ENV_LAMBDA_REGION_KEY,
    ENV_PRODUCTION
)

@patch('common.constants.os.getenv')
def test_get_global_environment(mock_getenv):
    mock_getenv.return_value = 'test_env'
    assert get_global_environment() == 'test_env'
    mock_getenv.assert_called_once_with(ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY)

@patch('common.constants.os.getenv')
def test_is_non_prod(mock_getenv):
    mock_getenv.return_value = ENV_PRODUCTION
    assert not is_non_prod()
    mock_getenv.return_value = 'dev'
    assert is_non_prod()

@patch('common.constants.os.getenv')
def test_get_region(mock_getenv):
    mock_getenv.return_value = 'us-west-2'
    assert get_region() == 'us-west-2'
    mock_getenv.assert_called_once_with(ENV_LAMBDA_REGION_KEY)

@patch('common.constants.os.getenv')
def test_get_logger_non_prod(mock_getenv):
    mock_getenv.return_value = 'dev'
    logger = get_logger()
    assert logger.level == logging.DEBUG

@patch('common.constants.os.getenv')
def test_get_logger_prod(mock_getenv):
    mock_getenv.return_value = ENV_PRODUCTION
    logger = get_logger()
    assert logger.level == logging.INFO

if __name__ == "__main__":
    pytest.main()