import logging
import os

ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY = "GLOBAL_ENVIRONMENT"


def get_global_environment():
    return os.getenv(ENV_LAMBDA_GLOBAL_ENVIRONMENT_KEY)


def get_logger():
    logger = logging.getLogger('CustomHandler')

    # create console handler and set level to debug
    if get_global_environment() == 'prod':
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    return logger

ENV_START_TIME_HOUR = 'START_TIME_HOUR'
ENV_START_TIME_MINUTE = 'START_TIME_MINUTE'
ENV_END_TIME_HOUR = 'END_TIME_HOUR'
ENV_END_TIME_MINUTE = 'END_TIME_MINUTE'
ENV_SAFETY_ZONE_START_HOUR = 'SAFETY_ZONE_START_HOUR'
ENV_SAFETY_ZONE_START_MINUTE = 'SAFETY_ZONE_START_MINUTE'
ENV_SAFETY_ZONE_END_HOUR = 'SAFETY_ZONE_END_HOUR'
ENV_SAFETY_ZONE_END_MINUTE = 'SAFETY_ZONE_END_MINUTE'
ENV_HOLIDAY_TABLE_NAME = "TABLE_NAME"
ENV_TARGET_LAMBDA_NAME = "TARGET_LAMBDA_NAME"
HOLIDAY_DATE_STR = "HOLIDAY_DATE"


ENV_RANDOM_SYSTEM_DB_CLUSTER_ARN = "DB_CLUSTER_ARN"
ENV_RANDOM_SYSTEM_DB_SECRET_ARN = "DB_SECRET_ARN"
ENV_RANDOM_SYSTEM_DB_NAME = "DB_NAME"
ENV_RANDOM_SYSTEM_OUTPUT_QUEUE_URL = "OUTPUT_QUEUE_URL"