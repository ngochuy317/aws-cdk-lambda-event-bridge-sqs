from aws_cdk import (
    Duration,
    Stack,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    aws_ec2 as ec2,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext

from apps.mulesoft_proxy.const import (
    ENV_LAMBDA_MULESOFT_CLIENT_ID,
    ENV_LAMBDA_MULESOFT_CLIENT_SECRET,
    ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT,
    ENV_STRATEGY_TABLE_NAME,
    ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT,
    ENV_LAMBDA_MULESOFT_USERNAME,
    ENV_LAMBDA_MULESOFT_PASSWORD,
    ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT,
)


class MulesoftProxyStack(Stack):
    AUTH_SCOPE_SMS_SEND = 'sms.send'
    AUTH_SERVER_NAME = 'mulesoft-proxy'

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.mulesoft_vpc = self.create_vpc()

        self.mulesoft_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(self.module_name()),
            function_name=self.execution_context.aws_lambda.create_resource_name(self.module_name()),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="mulesoft_proxy.handler.lambda_handler",
            environment={
                ENV_LAMBDA_MULESOFT_CLIENT_ID: ENV_LAMBDA_MULESOFT_CLIENT_ID,
                ENV_LAMBDA_MULESOFT_CLIENT_SECRET: ENV_LAMBDA_MULESOFT_CLIENT_SECRET,
                ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT: ENV_LAMBDA_MULESOFT_CUSTOMER_ACCOUNT_ENDPOINT,
                ENV_STRATEGY_TABLE_NAME: ENV_STRATEGY_TABLE_NAME,
                ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT: ENV_LAMBDA_MULESOFT_OUTREACH_ENDPOINT,
                ENV_LAMBDA_MULESOFT_USERNAME: ENV_LAMBDA_MULESOFT_USERNAME,
                ENV_LAMBDA_MULESOFT_PASSWORD: ENV_LAMBDA_MULESOFT_PASSWORD,
                ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT: ENV_LAMBDA_MULESOFT_POPUP_ENDPOINT,
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
            vpc=self.mulesoft_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[
                ec2.SecurityGroup(
                    self,
                    "MulesoftLambdaSecurityGroup",
                    vpc=self.mulesoft_vpc,
                    description="Security group for Lambda within VPC",
                    allow_all_outbound=True,
                )
            ]
        )
        self.mulesoft_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.execution_context.env_properties['region']}:{self.execution_context.env_properties['account_id']}:parameter/*"]
            )
        )

        self.cognito_server = self.create_cognito_server()
        self.api_gw = self.create_api_gateway()
        self.rest_auth = self.create_authorizer(self.cognito_server)
        self.add_resource(self.rest_auth, self.api_gw)

    def module_name(self) -> str:
        return 'mulesoft-proxy'

    def code_location(self) -> str:
        return 'mulesoft_proxy'

    def create_api_gateway(self) -> apigateway.RestApi:
        return apigateway.RestApi(
            self,
            "MulesoftProxyApi",
            rest_api_name="mulesoft-proxy-api",
            description="MulesoftProxyApi",
            cloud_watch_role=True,
            deploy=True,
            endpoint_types=[apigateway.EndpointType.REGIONAL]
        )

    def add_resource(
            self,
            authorizer: apigateway.CognitoUserPoolsAuthorizer,
            rest_api: apigateway.RestApi,
        ) -> None:

        mulesoft_lambda_integration = apigateway.LambdaIntegration(
            self.mulesoft_lambda,
            proxy=True,
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

        resource = rest_api.root.add_resource('mulesoft')
        resource.add_method(
            "POST",
            integration=mulesoft_lambda_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=[f'{self.get_auth_server_name()}/{self.AUTH_SCOPE_SMS_SEND}']
        ).add_method_response(status_code='200', response_models={"application/json": empty_model})

    def create_authorizer(self, user_pool: cognito.UserPool) -> apigateway.CognitoUserPoolsAuthorizer:
        return apigateway.CognitoUserPoolsAuthorizer(
            self,
            'MulesoftProxyCognitoAuthorizer',
            cognito_user_pools=[user_pool]
        )

    def get_auth_server_name(self) -> str:
        return f'{self.AUTH_SERVER_NAME}-{self.execution_context.get_short_env()}'
    
    def create_cognito_server(self) -> cognito.UserPool:
        user_pool = cognito.UserPool(
            self,
            'MulesoftProxyCognitoUserPool',
            self_sign_up_enabled=False,
            user_pool_name=self.get_auth_server_name()
        )
        user_pool.add_domain(
            'MulesoftProxyUserPoolDomain',
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=self.get_auth_server_name())
        )

        sms_scope = cognito.ResourceServerScope(
            scope_name=self.AUTH_SCOPE_SMS_SEND,
            scope_description='Sms send scope'
        )
        resource_server = user_pool.add_resource_server(
            'MulesoftProxyCognitoResourceServer',
            identifier=self.get_auth_server_name(),
            user_pool_resource_server_name=self.get_auth_server_name(),
            scopes=[sms_scope]
        )

        user_pool.add_client(
            'MulesoftProxyCognitoUserPoolClient',
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

    def create_vpc(self) -> ec2.Vpc:
        vpc = ec2.Vpc(
            self, 
            "MulesoftVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC
                ),
                ec2.SubnetConfiguration(
                    name="PrivateSubnet",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                )
            ]
        )
        return vpc