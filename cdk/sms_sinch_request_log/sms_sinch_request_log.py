from aws_cdk import (
    aws_dynamodb as dynamodb,
    Stack,
    RemovalPolicy,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext


class SmsSinchRequestLogStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.sms_sinch_request_log_table = dynamodb.Table(
            self,
            self.execution_context.aws_dynamo_db.create_resource_id("SmsSinchRequestLog"),
            table_name=f"{self.execution_context.get_short_env()}_SmsSinchRequestLog",
            partition_key=dynamodb.Attribute(
                name="unique_request_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
