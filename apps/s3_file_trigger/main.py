import json
import os
from s3_file_trigger.services.glue_service import GlueService
from s3_file_trigger.services.step_function_service import SfnService
from s3_file_trigger.services.etl_log_service import EtlLogService


etl_log_service = EtlLogService(etl_log_table=os.environ['ETL_LOG_TABLE'],
                                file_event_mapping_table=os.environ['FILE_EVENT_MAPPING_TABLE'],
                                file_event_lock_table=os.environ['FILE_EVENT_LOCK_TABLE'])
services = {
    "GLUE": GlueService(),
    "SFN": SfnService()
}


def lambda_handler(event, context):
    print(event)
    if event:
        s3event = json.loads(event["Records"][0]['body'])['Records'][0]['s3']
        process_event(s3event)

    return {
        'statusCode': 200,
        'body': json.dumps('OK')
    }


def process_event(event):
    event_config = etl_log_service.get_file_event_config(event['configurationId'])
    object_path = f's3:://{event["bucket"]["name"]}/{event["object"]["key"]}'
    object_version = event['object']['versionId']
    local_service = services[event_config['service']]

    if not event_config:
        raise Exception(f'No event mapping found for {event["configurationId"]}')

    if etl_log_service.is_object_processed(object_path, object_version):
        raise Exception(f'File {object_path} with {object_version} version id is already processed')

    if event_config['single_execution'] and local_service.is_running(event_config['target_arn']):
        raise Exception(f'Only 1 active run for {event["configurationId"]} of {event_config["target_arn"]} is allowed')

    execution_arn = local_service.run_async(object_path, event_config)
    etl_log_service.lock_processed_object(object_path, object_version, execution_arn)
    etl_log_service.create_etl_log_record(
        event_config["configuration_id"], event["bucket"]["name"], event["object"]["key"], execution_arn
    )
