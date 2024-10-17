import boto3


class DynamoDBService:
    def __init__(self, region, table_name):
        self.dynamo_table = boto3.resource('dynamodb', region).Table(table_name)

    def read_item(self, keys):
        response = self.dynamo_table.get_item(Key=keys)

        if response is not None and 'Item' in response:
            return response['Item']

        return None

    def update_item(self, item):
        self.dynamo_table.put_item(Item=item)
