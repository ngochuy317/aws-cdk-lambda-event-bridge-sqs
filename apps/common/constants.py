import logging
import os

ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY = "GLOBAL_ENVIRONMENT"
ENV_LAMBDA_MULESOFT_CLIENT_ID = "MULESOFT_CLIENT_ID"
ENV_LAMBDA_MULESOFT_CLIENT_SECRET = "MULESOFT_CLIENT_SECRET"
ENV_LAMBDA_MULESOFT_USERNAME = "MULESOFT_USERNAME"
ENV_LAMBDA_MULESOFT_PASSWORD = "MULESOFT_PASSWORD"
ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT = "MULESOFT_OUTREACH_ENDPOINT"
ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT = "MULESOFT_POPUP_ENDPOINT"
ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT = "MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT"



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