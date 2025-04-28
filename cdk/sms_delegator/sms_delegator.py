from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext

class SMSDelegatorStack(Stack):
    AUTH_SERVER_NAME = 'sms-delegator-auth-server'
    AUTH_SCOPE_SMS_SEND = 'sms_send'

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)


        self.table = dynamodb.Table(
            self,
            self.execution_context.aws_dynamo_db.create_resource_id(f"{self.module_name()}"),
            table_name=self.execution_context.aws_dynamo_db.create_resource_name(f"{self.module_name()}"),
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.check_message_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}"),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="sms_delegator.sms_delegator_lambda.handler",
            environment={
                
                "TABLE_NAME": self.table.table_name,
                "AWS_XRAY_CONTEXT_MISSING": "LOG_ERROR",
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
            tracing=_lambda.Tracing.ACTIVE,
        )
        self.table.grant_read_write_data(self.check_message_lambda)

        self.cognito_server = self.create_cognito_server()
        self.api_gw = self.create_api_gateway()
        self.rest_auth = self.create_authorizer(self.cognito_server)
        self.add_resource(self.rest_auth, self.api_gw, self.check_message_lambda)

    def module_name(self) -> str:
        return 'sms-delegator'
    
    def code_location(self) -> str:
        return 'sms_delegator'

    # def create_api_gateway_invoke_lambda_role(self, lambda_function: _lambda.Function):
    #     role = iam.Role(
    #         self,
    #         'ApiGatewayInvokeLambdaRole',
    #         assumed_by=iam.ServicePrincipal('apigateway.amazonaws.com'),
    #         role_name=self.execution_context.aws_iam.create_resource_name('api-gw-invoke-lambda')
    #     )
    #     lambda_function.grant_invoke(role)
    #     return role

    def add_resource(
            self,
            authorizer: apigateway.CognitoUserPoolsAuthorizer,
            rest_api: apigateway.RestApi,
            output_lambda: _lambda.Function,
        ) -> None:

        check_message_integration = apigateway.LambdaIntegration(
            handler=output_lambda,
            proxy=True
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

        resource = rest_api.root.add_resource('sms-delegator')
        resource.add_method(
            "POST",
            integration=check_message_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=[f'{self.get_auth_server_name()}/{self.AUTH_SCOPE_SMS_SEND}']
        ).add_method_response(status_code='200', response_models={"application/json": empty_model})

    def get_auth_server_name(self):
        return f'{self.AUTH_SERVER_NAME}-{self.execution_context.get_short_env()}'

    def create_cognito_server(self):
        user_pool = cognito.UserPool(
            self,
            'SMSDelegatorCognitoUserPool',
            self_sign_up_enabled=False,
            user_pool_name=self.get_auth_server_name()
        )
        user_pool.add_domain(
            'SMSDelegatorUserPoolDomain',
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=self.get_auth_server_name())
        )

        sms_scope = cognito.ResourceServerScope(
            scope_name=self.AUTH_SCOPE_SMS_SEND,
            scope_description='Sms send scope'
        )
        resource_server = user_pool.add_resource_server(
            'SMSDelegatorCognitoResourceServer',
            identifier=self.get_auth_server_name(),
            user_pool_resource_server_name=self.get_auth_server_name(),
            scopes=[sms_scope]
        )

        user_pool.add_client(
            'SMSDelegatorCognitoUserPoolClient',
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

    def create_api_gateway(self) -> apigateway.RestApi:
        return apigateway.RestApi(
            self,
            "SMSDelegatorApi",
            rest_api_name="sms-delegator-api",
            description="SMSDelegatorApi",
            cloud_watch_role=True,
            deploy=False,
            endpoint_types=[apigateway.EndpointType.REGIONAL]
        )
    
    def create_authorizer(self, user_pool: cognito.UserPool):
        return apigateway.CognitoUserPoolsAuthorizer(
            self,
            'SMSDelegatorCognitoAuthorizer',
            cognito_user_pools=[user_pool]
        )