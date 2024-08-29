import boto3


class LambdaClient:
    def __init__(self):
        self.lambda_client = boto3.client('lambda')

    def get_list_event_source_mappings(self, target_lambda_name: str) -> dict:
        return self.lambda_client.list_event_source_mappings(
            FunctionName=target_lambda_name
        )

    def get_event_source_mapping(self, uuid: str) -> dict:
        return self.lambda_client.get_event_source_mapping(
            UUID=uuid
        )

    def update_event_source_mapping(self, uuid: str, enabled: bool) -> dict:
        return self.lambda_client.update_event_source_mapping(
            UUID=uuid,
            Enabled=enabled
        )