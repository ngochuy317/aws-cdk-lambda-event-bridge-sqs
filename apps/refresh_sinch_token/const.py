# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring
import os
import logging

ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY = "GLOBAL_ENVIRONMENT"
ENV_DEVELOPMENT = 'dev'
ENV_STAGING = 'stg'
ENV_PRODUCTION = 'prod'
ENV_LAMBDA_SINCH_AUTH_URL = 'SINCH_AUTH_URL'
ENV_LAMBDA_SINCH_CLIENT_CREDENTIAL_PATH = 'SINCH_CLIENT_CREDENTIAL_PATH'


def get_global_environment():
    return os.getenv(ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY)


def is_non_prod():
    return get_global_environment() is not ENV_PRODUCTION


def get_logger():
    logger = logging.getLogger('CustomHandler')

    # create console handler and set level to debug
    if get_global_environment() == 'prod':
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    return logger
