import os
import sys
import logging


DEFAULT_FILE_SEPARATOR = '|'
DEFAULT_TIMESTAMP_MASK = "%Y-%m-%d %H:%M:%S"
ETL_FIELD_NAME = 'ProductExport'


def get_logger():
    logger = logging.getLogger('CustomHandler')

    log_handler = logging.StreamHandler(sys.stdout)

    # create console handler and set level to debug
    # create console handler and set level to debug
    if os.environ['GLOBAL_ENVIRONMENT'] == 'prod':
        logger.setLevel(logging.INFO)
        log_handler.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)
        log_handler.setLevel(logging.DEBUG)

    log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(log_format)

    logger.addHandler(log_handler)

    return logger
