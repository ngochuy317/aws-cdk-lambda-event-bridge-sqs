from aws_cdk import (
    Duration,
    Stack,
    aws_events as events,
    aws_apigateway as apigateway,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_iam as iam,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext

class MessageSubmitCallbacksStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.msg_submit_callbacks_event_bus = events.EventBus(
            self,
            self.execution_context.aws_event_rule.create_resource_id(f"{self.module_name()}-msg-submit-callbacks-event-bus"),
            event_bus_name=self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-msg-submit-callbacks-event-bus"),
        )

        self.message_submit_callbacks_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-msg-submit-callbacks"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-msg-submit-callbacks"),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="message_submit_callbacks.message_submit_callbacks_lambda.handler",
            environment={
                "EVENT_BUS_NAME": self.msg_submit_callbacks_event_bus.event_bus_name
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
        )
        self.msg_submit_callbacks_event_bus.grant_put_events_to(self.message_submit_callbacks_lambda)

        rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id(f"{self.module_name()}-event-rule"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-event-rule"),
            event_bus=self.msg_submit_callbacks_event_bus,
            event_pattern={
                "detail_type": ["message-submit"]
            })

        self.message_submit_callbacks_queue = self.create_fifo_queue("message-submit-callbacks")
        self.message_submit_callbacks_queue.grant_consume_messages(self.message_submit_callbacks_lambda)
        self.message_submit_callbacks_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.message_submit_callbacks_queue))

        self.create_api_gateway_sqs_role = self.create_api_gateway_role()
        self.api_gw = self.create_api_gateway()
        self.create_api_resources_and_methods()
    
    def module_name(self) -> str:
        return 'msg-submit-callbacks'

    def code_location(self) -> str:
        return 'message_submit_callbacks'
    
    def create_fifo_queue(self, queue_name) -> sqs.Queue:
        queue, _ = (
            self.execution_context.aws_sqs.create_fifo_queue(
                f"{self.module_name()}-{queue_name}",
                self,
                visibility_timeout=Duration.seconds(60)
            )
        )
        return queue
    
    def create_api_gateway(self) -> apigateway.RestApi:
        return apigateway.RestApi(
            self,
            "MessageSubmitCallbacksApi",
            rest_api_name="MessageSubmitCallbacksApi",
            description="MessageSubmitCallbacksApi",
        )
    
    def create_api_resources_and_methods(self) -> None:

        submit_message_integration = apigateway.AwsIntegration(
            service="sqs",
            path=f"{self.execution_context.env_properties['account_id']}/{self.message_submit_callbacks_queue.queue_name}",
            integration_http_method="POST",
            options=apigateway.IntegrationOptions(
                credentials_role=self.create_api_gateway_sqs_role,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
                },
                request_templates={
                    "application/json": (
                        "Action=SendMessage&MessageBody=$util.urlEncode($input.body)&MessageGroupId=111"
                    )
                },
                passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": '{"status": "message queued"}'
                        }
                    )
                ]
            )
        )

        # Add POST method to API Gateway resource
        self.api_gw.root.add_method(
            "POST",
            submit_message_integration,
            method_responses=[
                apigateway.MethodResponse(status_code="200")
            ]
        )

    def create_api_gateway_role(self) -> iam.Role:
        role = iam.Role(
            self,
            "ApiGatewaySqsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        role.add_to_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage", "sqs:ReceiveMessage"],
            resources=[self.message_submit_callbacks_queue.queue_arn]
        ))
        return role
