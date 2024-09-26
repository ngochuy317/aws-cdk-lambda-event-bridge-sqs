from http import HTTPStatus
import os
import json
import boto3
from mulesoft_proxy.const import (
    ENV_LAMBDA_MULESOFT_CLIENT_ID,
    ENV_LAMBDA_MULESOFT_CLIENT_SECRET,
    ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT,
    ENV_STRATEGY_TABLE_NAME,
    ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT,
    ENV_LAMBDA_MULESOFT_USERNAME,
    ENV_LAMBDA_MULESOFT_PASSWORD,
    ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT,
)
from mulesoft_proxy.service.mulesoft_service import MulesoftService
from common.ssm_service import SSMService
from common.constants import get_logger, get_global_environment

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.getenv(ENV_STRATEGY_TABLE_NAME))
logger = get_logger()
ssm_service = SSMService(logger=logger, env=get_global_environment())


def lambda_handler(event, context):
    try:
        logger.info("Lambda handler started")
        logger.debug(f"Event: {event}, Context: {context}")
        
        event_body_json = parse_event_body(event)
        mulesoft_service = create_mulesoft_service(ssm_service)
        
        proxy_name = event_body_json.get('proxy_name')
        if not proxy_name:
            return respond_with_error(HTTPStatus.BAD_REQUEST, "Missing required parameter: 'proxy_name'")
        
        customer_data_response = call_url_based_on_proxy_name(proxy_name, event_body_json, mulesoft_service)
        return customer_data_response
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in the event body: {e}")
        return respond_with_error(HTTPStatus.BAD_REQUEST, "Invalid JSON format")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return respond_with_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"An error occurred: {e}")


def parse_event_body(event):
    if not event or 'body' not in event:
        logger.error("Event body is missing")
        raise ValueError("Event body is missing")

    try:
        return json.loads(event['body'])
    except (TypeError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse event body: {e}")
        raise


def respond_with_error(status_code, message):
    return {
        'statusCode': status_code,
        'body': json.dumps({'message': message})
    }


def create_mulesoft_service(ssm_service):
    try:
        logger.debug("Creating Mulesoft service")
        client_id = get_ssm_parameter_safe(ENV_LAMBDA_MULESOFT_CLIENT_ID)
        client_secret = get_ssm_parameter_safe(ENV_LAMBDA_MULESOFT_CLIENT_SECRET)
        username = get_ssm_parameter_safe(ENV_LAMBDA_MULESOFT_USERNAME)
        password = get_ssm_parameter_safe(ENV_LAMBDA_MULESOFT_PASSWORD)
        
        return MulesoftService(client_id=client_id, client_secret=client_secret, username=username, password=password, logger=logger)
    except Exception as e:
        logger.error(f"Error creating Mulesoft service: {e}")
        raise

def get_ssm_parameter_safe(param_name):
    if not param_name:
        logger.error(f"SSM parameter name is empty")
        raise ValueError("SSM parameter name cannot be empty")
    
    try:
        return ssm_service.get_ssm_parameter_with_env(os.getenv(param_name))
    except Exception as e:
        logger.error(f"Failed to get SSM parameter '{param_name}': {e}")
        raise


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

def handle_update_popup(event_body_json, mulesoft_service):
    logger.info("Handling update popup")
    params = extract_params(event_body_json)
    logger.debug(f"Parameters extracted: {params}")
    return handle_request(event_body_json, mulesoft_service, ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT, method='PUT', body=params)

def handle_get_customer_account_with_strategy_table(event_body_json, mulesoft_service):
    logger.info("Handling get customer account with strategy table")
    customer_account = handle_get_customer_account(event_body_json, mulesoft_service)
    return enrich_customer_account_with_strategy(customer_account)

#TODO: Ideally need to refactor to a templatized approach versus needing to update lambda code for each new endpoint
def handle_request(event_body_json, mulesoft_service, endpoint, method='GET', body=None, headers=None, replace_phone_number=False):
    try:
        logger.info(f"Handling request with endpoint: {endpoint}")
        url = get_ssm_parameter_safe(endpoint)
        
        if replace_phone_number:
            url = replace_phone_number_in_url(url, event_body_json)
        
        return mulesoft_service.call_endpoint(url=url, method=method, body=body, headers=headers)
    except Exception as e:
        logger.error(f"Error in handle_request: {e}")
        raise

def extract_params(event_body_json):
    if not event_body_json:
        logger.warning("Event body JSON is empty")
        return {}
    logger.info("Extracting parameters from event_body_json")
    params = {}
    for key, value in event_body_json.get('proxy_metadata', {}).items():
        params[key] = value
    logger.info(f"Extracted parameters: {params}")
    return params

def replace_phone_number_in_url(url, event_body_json):
    try:
        print("event_body_json", event_body_json)
        phone_number = event_body_json['proxy_metadata']['phone_number']
        return url.replace("{phone_number}", phone_number)
    except KeyError as e:
        logger.error(f"Missing 'phone_number' in event body: {e}")
        raise ValueError(f"Missing 'phone_number' in event body: {e}")

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
