from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_lambda_event_sources as lambda_event_sources,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext


class SinchMessageDeliveryWebhook(Stack):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            sinch_sms_response_event_bus: events.EventBus,
            sms_sinch_request_log_table: dynamodb.Table,
            **kwargs
        ) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.account_id = self.execution_context.env_properties['account_id']
        self.sinch_sms_response_event_bus = sinch_sms_response_event_bus
        self.sms_sinch_request_log_table = sms_sinch_request_log_table

        self.sinch_message_delivery_webhook_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(self.module_name()),
            function_name=self.execution_context.aws_lambda.create_resource_name(self.module_name()),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="sinch_message_delivery_webhook.main.lambda_handler",
            environment={
                "REQUEST_LOG_TABLE": self.sms_sinch_request_log_table.table_name,
                "SMS_EVENT_BUS": self.sinch_sms_response_event_bus.event_bus_name,
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
        )
        self.sinch_message_delivery_webhook_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:PutItem"],
                resources=[f"arn:aws:dynamodb:{self.execution_context.env_properties['region']}:{self.account_id}:table/{self.sms_sinch_request_log_table.table_name}"]
            )
        )

        self.sinch_message_webhook_buffer_queue, _ = self.execution_context.aws_sqs.create_fifo_queue(
            self.execution_context.aws_sqs.create_resource_name("sinch-message-webhook-buffer"),
            self,
            visibility_timeout=Duration.seconds(40)
        )

        self.sinch_message_webhook_buffer_queue.grant_consume_messages(self.sinch_message_delivery_webhook_lambda)
        self.sinch_message_delivery_webhook_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.sinch_message_webhook_buffer_queue))
    
    def module_name(self) -> str:
        return 'sinch-message-delivery-webhook'

    def code_location(self) -> str:
        return 'sinch_message_delivery_webhook'