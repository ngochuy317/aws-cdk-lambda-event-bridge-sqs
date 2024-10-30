from aws_cdk import (
    Duration,
    Stack,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_apigateway as apigateway,
    aws_sqs as sqs,
    aws_lambda as _lambda,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext


class SinchRestApiStack(Stack):

    AUTH_SERVER_NAME = 'omf-sinch-app'
    AUTH_SCOPE_SINCH_PROXY = 'sinch.proxy'

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            sinch_proxy_buffer_queue: sqs.Queue,
            sinch_incoming_messages_webhook_lambda: _lambda.Function,
            sinch_message_webhook_buffer_queue: sqs.Queue,
            **kwargs
        ) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.account_id = self.execution_context.env_properties['account_id']
        self.sinch_proxy_buffer_queue = sinch_proxy_buffer_queue
        self.sinch_incoming_messages_webhook_lambda = sinch_incoming_messages_webhook_lambda
        self.sinch_message_webhook_buffer_queue = sinch_message_webhook_buffer_queue

        self.cognito_server = self.create_cognito_server()
        self.api_gw = self.create_api_gateway()
        self.rest_auth = self.create_authorizer(self.cognito_server)
        self.add_resource(self.rest_auth, self.api_gw)

    def module_name(self) -> str:
        return 'sinch-rest-api'

    def create_authorizer(self, user_pool: cognito.UserPool) -> apigateway.CognitoUserPoolsAuthorizer:
        return apigateway.CognitoUserPoolsAuthorizer(
            self,
            'SinchProxyCognitoAuthorizer',
            cognito_user_pools=[user_pool]
        )

    def create_api_gateway(self) -> apigateway.RestApi:
        return apigateway.RestApi(
            self,
            self.execution_context.aws_api_gateway.create_resource_id(self.module_name()),
            rest_api_name=self.execution_context.aws_api_gateway.create_resource_name(self.module_name()),
            description="SinchProxyApi",
            cloud_watch_role=True,
            deploy=True,
            endpoint_types=[apigateway.EndpointType.REGIONAL]
        )

    def create_api_role(self) -> iam.Role:
        role = iam.Role(
            self,
            self.execution_context.aws_role.create_resource_id(self.module_name()),
            assumed_by=iam.ServicePrincipal('apigateway.amazonaws.com'),
            role_name=self.execution_context.aws_role.create_resource_name('sinch-proxy-api')
        )

        self.sinch_proxy_buffer_queue.grant_send_messages(role)
        self.sinch_message_webhook_buffer_queue.grant_send_messages(role)
        self.sinch_incoming_messages_webhook_lambda.grant_invoke(role)
        return role
    
    def add_resource(
            self,
            authorizer: apigateway.CognitoUserPoolsAuthorizer,
            rest_api: apigateway.RestApi,
        ) -> None:

        api_role = self.create_api_role()
        submit_message_integration = apigateway.AwsIntegration(
            service="sqs",
            path=f"{self.account_id}/{self.sinch_proxy_buffer_queue.queue_name}",
            integration_http_method="POST",
            options=apigateway.IntegrationOptions(
                credentials_role=api_role,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
                },
                request_templates={
                    "application/json": (
                        "Action=SendMessage&"
                        "MessageGroupId=$util.urlEncode($util.escapeJavaScript($input.json('$.data[0].unique_request_id')))&"
                        "MessageDeduplicationId=$util.urlEncode($util.escapeJavaScript($input.json('$.data[0].unique_request_id')))&"
                        "MessageBody=$util.urlEncode($util.escapeJavaScript($input.json('$')))"
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

        sinch_resource = rest_api.root.add_resource('sinch')
        conversation_resource = sinch_resource.add_resource('conversation')
        conversation_resource.add_method(
            "POST",
            integration=submit_message_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=[f'{self.get_auth_server_name()}/{self.AUTH_SCOPE_SINCH_PROXY}']
        ).add_method_response(status_code='200', response_models={"application/json": empty_model})


        incoming_messages_webhook_integration = apigateway.AwsIntegration(
            service="lambda",
            path=f"2015-03-31/functions/{self.sinch_incoming_messages_webhook_lambda.function_arn}/invocations",
            integration_http_method="POST",
            options=apigateway.IntegrationOptions(
                credentials_role=api_role,
                integration_responses=[{
                    "statusCode": "200"
                }]
            )
        )

        auth_resource = rest_api.root.add_resource('auth')
        incoming_resource = auth_resource.add_resource('incoming')
        messages_resource = incoming_resource.add_resource('messages')
        messages_resource.add_method(
            "POST",
            integration=incoming_messages_webhook_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=[f'{self.get_auth_server_name()}/{self.AUTH_SCOPE_SINCH_PROXY}']
        ).add_method_response(status_code='200', response_models={"application/json": empty_model})


        sinch_proxy_message_delivery_integration = apigateway.AwsIntegration(
            service="sqs",
            path=f"{self.account_id}/{self.sinch_message_webhook_buffer_queue.queue_name}",
            integration_http_method="POST",
            options=apigateway.IntegrationOptions(
                credentials_role=api_role,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
                },
                request_templates={
                    "application/json": (
                        "Action=SendMessage&"
                        "MessageGroupId=$util.urlEncode($util.escapeJavaScript($input.json('$.message_delivery_report.message_id')))&"
                        "MessageBody=$util.urlEncode($util.escapeJavaScript($input.json('$')))"
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
        message_delivery_resource = sinch_resource.add_resource('message_delivery')
        message_delivery_resource.add_method(
            "POST",
            integration=sinch_proxy_message_delivery_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=[f'{self.get_auth_server_name()}/{self.AUTH_SCOPE_SINCH_PROXY}']
        ).add_method_response(status_code='200', response_models={"application/json": empty_model})



    def get_auth_server_name(self) -> str:
        return f'{self.account_id}-{self.AUTH_SERVER_NAME}-{self.execution_context.get_short_env()}'

    def create_cognito_server(self) -> cognito.UserPool:
        user_pool = cognito.UserPool(
            self,
            self.execution_context.aws_api_gateway.create_resource_name(self.module_name()),
            self_sign_up_enabled=False,
            user_pool_name=self.get_auth_server_name()
        )
        user_pool.add_domain(
            self.execution_context.aws_api_gateway.create_resource_id(self.module_name()),
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=self.get_auth_server_name())
        )

        sinch_proxy_scope = cognito.ResourceServerScope(
            scope_name=self.AUTH_SCOPE_SINCH_PROXY,
            scope_description='Sinch proxy scope'
        )
        resource_server = user_pool.add_resource_server(
            'SinchProxyCognitoResourceServer',
            identifier=self.get_auth_server_name(),
            user_pool_resource_server_name=self.get_auth_server_name(),
            scopes=[sinch_proxy_scope]
        )

        user_pool.add_client(
            'SinchProxyCognitoUserPoolClient',
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
                scopes=[cognito.OAuthScope.resource_server(resource_server, sinch_proxy_scope)]
            ),
            prevent_user_existence_errors=True,
            generate_secret=True)

        return user_pool