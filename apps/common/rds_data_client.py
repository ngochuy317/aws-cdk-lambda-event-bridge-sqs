import boto3
from botocore.exceptions import ClientError


class RDSDataClient:
    def __init__(self):
        self.rds_data_client = boto3.client('rds-data')

    def execute_statement(self, sql: str, parameters: list, cluster_arn: str, secret_arn: str, db_name: str):
        try:
            response = self.rds_data_client.execute_statement(
                secretArn=secret_arn,
                database=db_name,
                resourceArn=cluster_arn,
                sql=sql,
                parameters=parameters
            )
            return response
        except ClientError as e:
            print(f"Error executing SQL statement: {e}")
            raise e
