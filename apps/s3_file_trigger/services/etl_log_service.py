from datetime import datetime
import boto3


class EtlLogService:
    def __init__(self, etl_log_table, file_event_mapping_table, file_event_lock_table):
        self.dynamodb = boto3.resource('dynamodb')
        self.config_table = self.dynamodb.Table(file_event_mapping_table)
        self.lock_table = self.dynamodb.Table(file_event_lock_table)
        self.etl_log_table = self.dynamodb.Table(etl_log_table)

    def get_file_event_config(self, config_id):
        key = {
            'configuration_id': config_id
        }
        response = self.config_table.get_item(Key=key)

        if 'Item' in response:
            return response['Item']

        return None

    def lock_processed_object(self, object_name, object_version, execution_arn):
        item = {
            'object_path': object_name,
            'object_version': object_version,
            'execution_arn': execution_arn,
            'process_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self.lock_table.put_item(Item=item)

    def create_etl_log_record(self, item_name, object_bucket, object_key, execution_arn):
        execution_time = datetime.now().strftime("%Y-%m-%d'T'%H:%M:%S")
        item = {
            "item": item_name,
            "etl_name": "ProductExport",
            "dest_bucket": object_bucket,
            "dest_path": object_key,
            "end_date": execution_time,
            "is_completed": "true",
            "offset": "1",
            "requestId": execution_arn,
            "start_date": execution_time
        }

        self.etl_log_table.put_item(Item=item)

    def is_object_processed(self, object_name, object_version):
        key = {
            'object_path': object_name,
            'object_version': object_version
        }
        response = self.lock_table.get_item(Key=key)

        if 'Item' in response:
            return response['Item']

        return None
