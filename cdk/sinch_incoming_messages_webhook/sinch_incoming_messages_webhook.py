from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext


class SinchIncomingMessagesWebhookStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, sinch_sms_response_event_bus: events.EventBus, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.sinch_sms_response_event_bus = sinch_sms_response_event_bus

        self.incoming_message_topic = sns.Topic(
            self,
            self.execution_context.aws_sns.create_resource_id("sinch-sms-response"),
            topic_name=self.execution_context.aws_sns.create_resource_name("sinch-sms-response"),
            display_name="New Account Notifications"
        )
        self.process_sinch_sms_response_sqs, _ = self.execution_context.aws_sqs.create_standard_queue(
            self.execution_context.aws_sqs.create_resource_name("process-sinch-sms-response"),
            self,
            visibility_timeout=Duration.seconds(40)
        )
        self.incoming_message_topic.add_subscription(subscriptions.SqsSubscription(self.process_sinch_sms_response_sqs))

        self.sinch_incoming_messages_webhook_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(self.module_name()),
            function_name=self.execution_context.aws_lambda.create_resource_name(self.module_name()),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="sinch_incoming_messages_webhook.main.lambda_handler",
            environment={
                "EVENT_BUS_SINCH_MESSAGES": self.sinch_sms_response_event_bus.event_bus_name,
                "SINCH_SNS": self.incoming_message_topic.topic_arn,
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
        )
        self.incoming_message_topic.grant_publish(self.sinch_incoming_messages_webhook_lambda)

    def module_name(self) -> str:
        return 'sinch-incoming-messages-webhook'

    def code_location(self) -> str:
        return 'sinch_incoming_messages_webhook'

    
