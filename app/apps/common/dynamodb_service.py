import boto3


class DynamoDBService:
    def __init__(self, table_name):
        self.dynamo_table = boto3.resource('dynamodb').Table(table_name)

    def get_item(self, key: dict) -> dict:
        response = self.dynamo_table.get_item(Key=key)
        return response

    def get_items(self):
        response = self.dynamo_table.scan()
        return response
