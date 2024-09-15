from common.constants import get_logger

# Set up logging
logger = get_logger()


def lambda_handler(event, context):

    logger.info(f"Received event: {event} with context: {context}")
