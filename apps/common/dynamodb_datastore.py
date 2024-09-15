import boto3
import botocore.exceptions
from boto3.dynamodb.conditions import Key


class Datastore:
    def get_item(self, key, fields=None):
        pass

    def put(self, item):
        pass


# Make it common, not SMS specific
class DynamoDbDatastore(Datastore):
    DYNAMO_CLIENT_TIMEOUT = 900

    def __init__(self, table, logger, role_arn=None):
        self.role_arn = role_arn
        self.table_name = table
        self.logger = logger

        if role_arn:
            self.table = self.prepare_cross_account_table()
        else:
            self.table = boto3.resource('dynamodb').Table(self.table_name)

    def prepare_cross_account_table(self):
        sts_client = boto3.client('sts')
        response = sts_client.assume_role(RoleArn=self.role_arn,
                                          RoleSessionName='RoleSessionName',
                                          DurationSeconds=self.DYNAMO_CLIENT_TIMEOUT)

        return boto3.resource('dynamodb', region_name='us-east-1',
                              aws_access_key_id=response['Credentials']['AccessKeyId'],
                              aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                              aws_session_token=response['Credentials']['SessionToken']).Table(self.table_name)

    @staticmethod
    def create_select_projection(fields):
        if fields:
            projection_expr = []
            expression_names = {}

            for field in fields:
                projected = f'#{field}'
                projection_expr.append(projected)
                expression_names[projected] = field

            return ','.join(projection_expr), expression_names

        return None, None

    def get_item(self, key, fields=None):
        return self.call_with_cross_acc(lambda: self._get_item(key, fields))

    def query_item(self, key_field, key_value, fields=None):
        return self.call_with_cross_acc(lambda: self._query_item(key_field, key_value, fields))

    def put(self, item):
        return self.call_with_cross_acc(lambda: self._store(item))

    def _get_item(self, key, fields):
        if fields:
            projection_expr, expression_names = self.create_select_projection(fields)
            self.logger.debug("Looking for %s as %s", projection_expr, expression_names)
            response = self.table.get_item(Key=key,
                                           ProjectionExpression=projection_expr,
                                           ExpressionAttributeNames=expression_names)
        else:
            response = self.table.get_item(Key=key)

        return response.get('Item')

    def _query_item(self, key_field, key_value, fields):
        args = {
            'KeyConditionExpression': Key(key_field).eq(key_value)
        }

        if fields:
            projection_expr, expression_names = self.create_select_projection(fields)
            self.logger.debug("Looking for %s as %s", projection_expr, expression_names)
            args['ProjectionExpression'] = projection_expr
            args['ExpressionAttributeNames'] = expression_names

        response = self.table.query(**args)

        if response.get('Items'):
            return response['Items'][0]

        return None

    def _store(self, item):
        self.table.put_item(Item=item)

    def call_with_cross_acc(self, call_func):
        try:
            return call_func()
        except botocore.exceptions.ClientError as error:
            if self.role_arn and error.response['Error']['Code'] == 'ExpiredTokenException':
                self.logger.warning('Cross account token expired. Refreshing...')
                self.table = self.prepare_cross_account_table()
                return call_func()

            self.logger.error('Call failed with %s', error)
            raise error
