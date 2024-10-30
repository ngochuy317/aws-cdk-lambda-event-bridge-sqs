from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_lambda_event_sources as lambda_event_sources,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext


class SinchServiceStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, sms_sinch_request_log_table: dynamodb.Table, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.account_id = self.execution_context.env_properties['account_id']
        self.sms_sinch_request_log_table = sms_sinch_request_log_table
        self.sinch_proxy_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(self.module_name()),
            function_name=self.execution_context.aws_lambda.create_resource_name(self.module_name()),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="sinch_proxy.main.lambda_handler",
            environment={
                "GLOBAL_ENVIRONMENT": self.execution_context.get_short_env(),
                "REQUEST_LOG_TABLE": self.sms_sinch_request_log_table.table_name,
                "SINCH_CLIENT_CREDENTIAL_PATH": "/http/sinch/api/client_credentials/",
                "REFRESH_INTERVAL_MINUTES": "15",
                "MA_MESSAGE_DELIVERY_CALLBACK_URL": "/http/sinch/callback/message_delivery",
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
        )

        self.sinch_proxy_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions= [
                "ssm:GetParameter",
                "ssm:PutParameter",
                "ssm:GetParametersByPath"
            ],
                resources=[f"arn:aws:ssm:{self.execution_context.env_properties['region']}:{self.account_id}:parameter/{self.execution_context.get_short_env()}/*"]
            )
        )
        self.sinch_proxy_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:PutItem"],
                resources=[f"arn:aws:dynamodb:{self.execution_context.env_properties['region']}:{self.account_id}:table/{self.sms_sinch_request_log_table.table_name}"]
            )
        )

        self.sinch_proxy_buffer_queue, _ = self.execution_context.aws_sqs.create_fifo_queue(
            self.execution_context.aws_sqs.create_resource_name(f"{self.module_name()}-buffer"),
            self,
            visibility_timeout=Duration.seconds(40)
        )
        self.sinch_proxy_buffer_queue.grant_consume_messages(self.sinch_proxy_lambda)
        self.sinch_proxy_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.sinch_proxy_buffer_queue))

        self.create_ssm_parameters()

    def create_ssm_parameters(self) -> None:
        ssm_sinch_callback_message_delivery_url = self.execution_context.aws_ssm.create_ssm_parameter_placeholder(
            self, "http/sinch/callback/message_delivery", "Sinch callback message delivery endpoint")

    def module_name(self) -> str:
        return 'sinch-proxy'

    def code_location(self) -> str:
        return 'sinch_proxy'
