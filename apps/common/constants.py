import logging
import os

ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY = "GLOBAL_ENVIRONMENT"


def get_global_environment():
    return os.getenv(ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY)


def is_non_prod():
    return get_global_environment() != 'prod'


def get_logger():
    logger = logging.getLogger('CustomHandler')

    # create console handler and set level to debug
    if get_global_environment() == 'prod':
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    return logger