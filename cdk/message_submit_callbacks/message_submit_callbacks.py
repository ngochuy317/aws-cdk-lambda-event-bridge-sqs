from aws_cdk import (
    Duration,
    Stack,
    aws_cognito as cognito,
    aws_events as events,
    aws_events_targets as targets,
    aws_apigateway as apigateway,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_iam as iam,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext

class MessageSubmitCallbacksStack(Stack):
    AUTH_SCOPE_SMS_SEND = 'sms.send'
    AUTH_SERVER_NAME = 'ods'

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.msg_submit_callbacks_event_bus = events.EventBus(
            self,
            self.execution_context.aws_event_bus.create_resource_id(f"{self.module_name()}"),
            event_bus_name=self.execution_context.aws_event_bus.create_resource_name(f"{self.module_name()}"),
        )

        self.message_submit_callbacks_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}"),
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
            self.execution_context.aws_event_rule.create_resource_id(f"{self.module_name()}"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}"),
            event_bus=self.msg_submit_callbacks_event_bus,
            event_pattern={
                "detail_type": ["message-submit"]
            })
        
        target_lambda = _lambda.Function(
            self,
            "TargetLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="message_submit_callbacks.target_lambda.handler"
        )
        rule.add_target(targets.LambdaFunction(target_lambda))

        self.message_submit_callbacks_queue = self.create_fifo_queue("message-submit-callbacks")
        self.message_submit_callbacks_queue.grant_consume_messages(self.message_submit_callbacks_lambda)
        self.message_submit_callbacks_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.message_submit_callbacks_queue))

        self.cognito_server = self.create_cognito_server()
        self.api_gw = self.create_api_gateway()
        self.rest_auth = self.create_authorizer(self.cognito_server)
        self.add_resource(self.rest_auth, self.api_gw, self.message_submit_callbacks_queue)
    
    def module_name(self) -> str:
        return 'message-submit-callbacks'

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
            rest_api_name="message-submit-callbacks-api",
            description="MessageSubmitCallbacksApi",
            cloud_watch_role=True,
            deploy=False,
            endpoint_types=[apigateway.EndpointType.REGIONAL]
        )
    
    def create_api_role(self, output_queue: sqs.Queue):
        role = iam.Role(
            self,
            'OdsApiGatewayRole',
            assumed_by=iam.ServicePrincipal('apigateway.amazonaws.com'),
            role_name=self.execution_context.aws_iam.create_resource_name('ods-api')
        )

        output_queue.grant_send_messages(role)
        return role
    
    def add_resource(
            self,
            authorizer: apigateway.CognitoUserPoolsAuthorizer,
            rest_api: apigateway.RestApi,
            output_queue: sqs.Queue
        ) -> None:

        api_role = self.create_api_role(output_queue)
        submit_message_integration = apigateway.AwsIntegration(
            service="sqs",
            path=f"{self.execution_context.env_properties['account_id']}/{output_queue.queue_name}",
            integration_http_method="POST",
            options=apigateway.IntegrationOptions(
                credentials_role=api_role,
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

        empty_model = rest_api.add_model(
            "EmptyResponseModel",
            content_type="application/json",
            model_name="EmptyResponseModel",
            schema=apigateway.JsonSchema(
            schema=apigateway.JsonSchemaVersion.DRAFT4,
            title="Empty schema",
            type=apigateway.JsonSchemaType.OBJECT)
        )

        resource = rest_api.root.add_resource('sinch').add_resource('submit')
        resource.add_method(
            "POST",
            integration=submit_message_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=[f'{self.get_auth_server_name()}/{self.AUTH_SCOPE_SMS_SEND}']
        ).add_method_response(status_code='200', response_models={"application/json": empty_model})
    
    def create_authorizer(self, user_pool: cognito.UserPool):
        return apigateway.CognitoUserPoolsAuthorizer(
            self,
            'OdsCognitoAuthorizer',
            cognito_user_pools=[user_pool]
        )
    
    def get_auth_server_name(self):
        return f'{self.AUTH_SERVER_NAME}-{self.execution_context.get_short_env()}'
    
    def create_cognito_server(self):
        user_pool = cognito.UserPool(
            self,
            'OdsCognitoUserPool',
            self_sign_up_enabled=False,
            user_pool_name=self.get_auth_server_name()
        )
        user_pool.add_domain(
            'OdsUserPoolDomain',
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=self.get_auth_server_name())
        )

        sms_scope = cognito.ResourceServerScope(
            scope_name=self.AUTH_SCOPE_SMS_SEND,
            scope_description='Sms send scope'
        )
        resource_server = user_pool.add_resource_server(
            'OdsCognitoResourceServer',
            identifier=self.get_auth_server_name(),
            user_pool_resource_server_name=self.get_auth_server_name(),
            scopes=[sms_scope]
        )

        user_pool.add_client(
            'OdsCognitoUserPoolClient',
            user_pool_client_name=self.get_auth_server_name(),
            id_token_validity=Duration.days(1),
            access_token_validity=Duration.days(1),
            auth_flows=cognito.AuthFlow(
                user_password=False,
                user_srp=False,
                custom=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=False,
                    implicit_code_grant=False,
                    client_credentials=True
                ),
                scopes=[cognito.OAuthScope.resource_server(resource_server, sms_scope)]
            ),
            prevent_user_existence_errors=True,
            generate_secret=True)

        return user_pool
