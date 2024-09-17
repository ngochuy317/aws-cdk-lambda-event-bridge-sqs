from common.constants import (
    ENV_LAMBDA_MULESOFT_CLIENT_ID,
    ENV_LAMBDA_MULESOFT_CLIENT_SECRET,
    ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT,
    ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT,
    ENV_LAMBDA_MULESOFT_USERNAME,
    ENV_LAMBDA_MULESOFT_PASSWORD,
    ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT,
    get_logger,
    get_global_environment
)
import json
import os
from http import HTTPStatus

from common.ssm_service import SSMService
from service.mulesoft_service import MulesoftService

# Set up logging
logger = get_logger()
ssm_service = SSMService(logger=logger, env=get_global_environment())


def lambda_handler(event, context):

    logger.info(f"Received event: {event} with context: {context}")

    for record in event['Records']:
        try:
            # Parse the SQS message body
            message = json.loads(record['body'])
            transformed_data = {
                "transaction_correlation_id": message.get("transaction_correlation_id"),
                "from": message.get("from"),
                "to": message.get("to"),
                "sms_message": message.get("sms_message"),
                "sms_message_id": message.get("sms_message_id"),
                "event_timestamp": message.get("event_timestamp"),
                "event_type": message.get("event_type"),
                "source_sender": message.get("source_sender"),
            }

            transformed_data["sms_metadata"] = {
                "application_number": "7777777",
                "lead_number": "8237894"
            }

            mulesoft_service = create_mulesoft_service(ssm_service)
        except Exception as ex:
            logger.exception(f"error: {ex}")

def create_mulesoft_service(ssm_service):
    logger.debug("Creating Mulesoft service")
    mulesoft_service = MulesoftService(
        client_id=ssm_service.get_ssm_parameter_with_env(os.getenv(ENV_LAMBDA_MULESOFT_CLIENT_ID)),
        client_secret=ssm_service.get_ssm_parameter_with_env(os.getenv(ENV_LAMBDA_MULESOFT_CLIENT_SECRET)),
        username=ssm_service.get_ssm_parameter_with_env(os.getenv(ENV_LAMBDA_MULESOFT_USERNAME)),
        password=ssm_service.get_ssm_parameter_with_env(os.getenv(ENV_LAMBDA_MULESOFT_PASSWORD)),
        logger=logger
    )
    return mulesoft_service

def replace_phone_number_in_url(url, event_body_json):
    logger.info("Replacing phone number in URL")
    phone_number = event_body_json['proxy_metadata']['phone_number']
    logger.info(f"Phone number: {phone_number}")
    return url.replace("{phone_number}", phone_number)

def handle_request(event_body_json, mulesoft_service, endpoint, method='GET', body=None, headers=None, replace_phone_number=False):
    logger.info(f"Handling request with event_body_json: {event_body_json}, endpoint: {endpoint}, method: {method}, body: {body}, headers: {headers}, replace_phone_number: {replace_phone_number}")
    url = ssm_service.get_ssm_parameter_with_env(os.getenv(endpoint))
    if replace_phone_number:
        logger.info("Replacing phone number in URL")
        url = replace_phone_number_in_url(url, event_body_json)
    logger.info(f"Final URL: {url}")
    return mulesoft_service.call_endpoint(url=url, method=method, body=body, headers=headers)

def extract_params(event_body_json):
    logger.info("Extracting parameters from event_body_json")
    params = {}
    for key, value in event_body_json.get('proxy_metadata', {}).items():
        params[key] = value
    logger.info(f"Extracted parameters: {params}")
    return params

def handle_check_outreach_count(event_body_json, mulesoft_service):
    logger.info("Handling check outreach count")
    params = extract_params(event_body_json)
    logger.debug(f"Parameters extracted: {params}")
    return handle_request(event_body_json, mulesoft_service, ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT, headers=params)

def handle_get_customer_account(event_body_json, mulesoft_service):
    logger.info("Handling get customer account")
    return handle_request(event_body_json, mulesoft_service, ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT, replace_phone_number=True)

def handle_update_customer_account(event_body_json, mulesoft_service):
    logger.info("Handling update customer account")
    params = extract_params(event_body_json)
    logger.debug(f"Parameters extracted: {params}")
    return handle_request(event_body_json, mulesoft_service, ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT, method='PUT', body=params)


def enrich_customer_account_with_strategy(customer_account):
    logger.info(f"Enriching customer account with strategy data: {customer_account}")

    # Decode and parse the body data
    body_bytes = customer_account['body']
    body_str = body_bytes.decode('utf-8')
    body_data = json.loads(body_str)

    for record in body_data:
        score_account_id = record.get('score_account_id')
        logger.info(f"Extracted Score Account ID: {score_account_id}")

        strategy_data = {
            'product': '',
            'site': '',
            'bom_dq': '',
            'strategy_month_end_date': ''
        }

        if not score_account_id:
            logger.warning(f"No score_account_id found in record: {record}")
        else:
            try:
                response = table.get_item(Key={'UAI_ID': score_account_id})
                item = response.get('Item', {})
                if item:
                    strategy_data.update({
                        'product': item.get('PRODUCT', ''),
                        'site': item.get('SITE', ''),
                        'bom_dq': item.get('BOM_DQ', ''),
                        'strategy_month_end_date': item.get('PRD_END_DATE', '')
                    })
            except Exception as e:
                logger.error(f"Failed to fetch strategy data for {score_account_id}: {e}")

        record.update(strategy_data)

    # Convert the Python object back to a JSON string and update the body in customer_account
    new_body_str = json.dumps(body_data)
    customer_account['body'] = new_body_str.encode('utf-8')

    return customer_account

def handle_update_popup(event_body_json, mulesoft_service):
    logger.info("Handling update popup")
    params = extract_params(event_body_json)
    logger.debug(f"Parameters extracted: {params}")
    return handle_request(event_body_json, mulesoft_service, ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT, method='PUT', body=params)

def handle_get_customer_account_with_strategy_table(event_body_json, mulesoft_service):
    logger.info("Handling get customer account with strategy table")
    customer_account = handle_get_customer_account(event_body_json, mulesoft_service)
    return enrich_customer_account_with_strategy(customer_account)


def get_proxy_handlers():
    logger.debug("Getting proxy handlers")
    proxy_handlers = {
        "get_customer_outreach": handle_check_outreach_count,
        "get_customer_account_branch_info": handle_get_customer_account,
        "update_customer_outreach": handle_update_customer_account,
        "update_popup": handle_update_popup,
        "get_customer_account_branch_info_with_strategy_data": handle_get_customer_account_with_strategy_table
    }
    logger.info(f"Proxy handlers: {proxy_handlers}")
    return proxy_handlers

def call_url_based_on_proxy_name(proxy_name, event_body_json, mulesoft_service):
    logger.debug(f"Calling URL based on proxy name: {proxy_name}")
    proxy_handlers = get_proxy_handlers()
    if proxy_name not in proxy_handlers:
        logger.error(f"Unknown proxy_name: {proxy_name}")
        return {
            'statusCode': HTTPStatus.BAD_REQUEST,
            'body': json.dumps({'message': "Unknown parameter: 'proxy_name'. Not an accepted value"})
        }

    return proxy_handlers[proxy_name](event_body_json, mulesoft_service)
