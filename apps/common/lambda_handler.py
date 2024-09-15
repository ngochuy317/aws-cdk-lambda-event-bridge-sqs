import functools

from common.constants import get_logger


def lambda_batch_handler(_func=None, *, my_logger=None):
    def decorator_lambda_handler(func):
        @functools.wraps(func)
        def wrap(event, context):
            logger = my_logger if my_logger else get_logger()

            logger.debug("Processing %s", event)
            # Handle batch failures
            batch_item_failures = []
            sqs_batch_response = {}
            event_id = None

            for sms_event in event["Records"]:
                try:
                    func(event, context)
                    logger.info("Successfully processed %s event.", event_id)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Event %s with queue message id %s failed due to %s", event_id, sms_event['messageId'], e)
                    batch_item_failures.append({"itemIdentifier": sms_event['messageId']})

            # Handle batch failures
            sqs_batch_response["batchItemFailures"] = batch_item_failures
            return sqs_batch_response
        return wrap

    if _func is None:
        return decorator_lambda_handler
    else:
        return decorator_lambda_handler(_func)
