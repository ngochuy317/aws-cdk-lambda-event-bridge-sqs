import os
import json
from contact_pro_post_handler.const import get_logger, get_global_environment
from contact_pro_post_handler.service.ssm_service import SSMService
from contact_pro_post_handler.service.contact_pro_service import ContactProService


logger = get_logger()
ssm_service = SSMService(logger, get_global_environment())
contact_pro_service = ContactProService(
    username=ssm_service.get_ssm_parameter_with_env(os.getenv('CONTACT_PRO_USERNAME')),
    password=ssm_service.get_ssm_parameter_with_env(os.getenv('CONTACT_PRO_PASSWORD')),
    base_path=ssm_service.get_ssm_parameter_with_env(os.getenv('CONTACT_PRO_BASE_URL')),
    x_api_key=ssm_service.get_ssm_parameter_with_env(os.getenv('CONTACT_PRO_X_API_KEY')),
    logger=logger
)


def lambda_handler(event, context):
    for single_event in event['Records']:
        logger.debug(single_event)
        parsed_event = json.loads(single_event['body'])

        if is_not_duplicate(parsed_event, single_event["attributes"]):
            message_id = contact_pro_service.post_event_to_contact_pro(
                endpoint_path=parsed_event['api_path'],
                body=parsed_event['api_post_body']
            )

            logger.info("Request %s was successfully posted to Contact pro with %s message id.", parsed_event['unique_request_id'], message_id)
        else:
            logger.warning("Request %s was already processed: %s receives", parsed_event['unique_request_id'], single_event["attributes"]["ApproximateReceiveCount"])


# Event hasn't been retried yet (ApproximateReceiveCount==1)
# Event is not a duplicate (the source Lambda posted it twice - 'duplicate_event' in event and event_attributes['duplicate_event'])
# Event doesn't exist in ContactPro (get returns empty array)
def is_not_duplicate(event, event_attributes):
    is_duplicate = 'duplicate_event' in event and event['duplicate_event']
    if not is_duplicate and event_attributes["ApproximateReceiveCount"] == '1':
        return True

    logger.warning("Request %s was received more %s times with %s duplicate flag, checking if it was successfully posted to ContactPro before.", event['unique_request_id'], is_duplicate, event_attributes["ApproximateReceiveCount"])
    return len(contact_pro_service.get_event_from_contact_pro(event['api_path'], event['api_get_body'])) == 0
