from aws_cdk import (
    Duration,
    Stack,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_apigateway as apigateway,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as _lambda,
    aws_ec2 as ec2,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    aws_cloudwatch_actions as actions,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext



class RefreshSinchTokenStack(Stack):

    AUTH_SERVER_NAME = 'refresh-sinch-token'
    AUTH_SCOPE_REFRESH_SINCH_TOKEN = 'sinch-token.refresh'
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.refresh_sinch_token_vpc = self.create_vpc()

        self.refresh_sinch_token_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(self.module_name()),
            function_name=self.execution_context.aws_lambda.create_resource_name(self.module_name()),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="refresh_sinch_token.handler.lambda_handler",
            environment={},
            runtime=_lambda.Runtime.PYTHON_3_9,
            tracing=_lambda.Tracing.ACTIVE,
            vpc=self.refresh_sinch_token_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[
                ec2.SecurityGroup(
                    self,
                    "RefreshSinchTokenLambdaSecurityGroup",
                    vpc=self.refresh_sinch_token_vpc,
                    description="Security group for Lambda within VPC",
                    allow_all_outbound=True,
                )
            ]
        )

        self.refresh_sinch_token_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.execution_context.env_properties['region']}:{self.execution_context.env_properties['account_id']}:parameter/*"]
            )
        )

        self.create_lambda_monitoring()

        self.cognito_server = self.create_cognito_server()
        self.api_gw = self.create_api_gateway()
        self.rest_auth = self.create_authorizer(self.cognito_server)
        self.add_resource(self.rest_auth, self.api_gw)

    def create_lambda_monitoring(self):
        sns_topic = sns.Topic(self, "RefreshSinchTokenLambdaAlertsTopic")

        error_alarm = cloudwatch.Alarm(self, "RefreshSinchTokenLambdaErrorAlarm",
            metric=self.refresh_sinch_token_lambda.metric_errors(),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm for Lambda function errors",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        )
        error_alarm.add_alarm_action(actions.SnsAction(sns_topic))

        duration_alarm = cloudwatch.Alarm(self, "RefreshSinchTokenLambdaDurationAlarm",
            metric=self.refresh_sinch_token_lambda.metric_duration(),
            threshold=5000,
            evaluation_periods=1,
            alarm_description="Alarm if Lambda execution duration exceeds 5 seconds",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        duration_alarm.add_alarm_action(actions.SnsAction(sns_topic))

        # Throttle alarm: if the function gets throttled due to exceeding concurrency limits
        throttle_alarm = cloudwatch.Alarm(self, "RefreshSinchTokenLambdaThrottleAlarm",
            metric=self.refresh_sinch_token_lambda.metric_throttles(),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm for Lambda function throttles",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        )
        throttle_alarm.add_alarm_action(actions.SnsAction(sns_topic))

        invocation_alarm = cloudwatch.Alarm(self, "RefreshSinchTokenLambdaInvocationAlarm",
            metric=self.refresh_sinch_token_lambda.metric_invocations(),
            threshold=100,  # Customize based on expected traffic
            evaluation_periods=1,
            alarm_description="Alarm if Lambda function is invoked more than 100 times",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        )
        invocation_alarm.add_alarm_action(actions.SnsAction(sns_topic))

    def create_authorizer(self, user_pool: cognito.UserPool) -> apigateway.CognitoUserPoolsAuthorizer:
        return apigateway.CognitoUserPoolsAuthorizer(
            self,
            'RefreshSinchTokenCognitoAuthorizer',
            cognito_user_pools=[user_pool]
        )

    def get_auth_server_name(self) -> str:
        return f'{self.AUTH_SERVER_NAME}-{self.execution_context.get_short_env()}'
    
    def create_api_gateway(self) -> apigateway.RestApi:
        return apigateway.RestApi(
            self,
            "RefreshSinchTokenApi",
            rest_api_name="refresh-sinch-token-api",
            description="RefreshSinchTokenApi",
            cloud_watch_role=True,
            deploy=True,
            deploy_options=apigateway.StageOptions(
                tracing_enabled=True
            ),
            endpoint_types=[apigateway.EndpointType.REGIONAL]
        )

    def add_resource(
            self,
            authorizer: apigateway.CognitoUserPoolsAuthorizer,
            rest_api: apigateway.RestApi,
        ) -> None:

        refresh_sinch_token_event_bus = events.EventBus(
            self,
            self.execution_context.aws_event_bus.create_resource_id(self.module_name()),
            event_bus_name=self.execution_context.aws_event_bus.create_resource_name(self.module_name()),
        )

        refresh_sinch_token_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_name(self.module_name()),
            rule_name=self.execution_context.aws_event_rule.create_resource_name(self.module_name()),
            event_pattern={
                "source": ["api-gateway"],
                "detail_type": ["API Gateway Proxy"]
            },
            event_bus=refresh_sinch_token_event_bus,
        )

        refresh_sinch_token_rule_integration = apigateway.AwsIntegration(
            service="events",
            action="PutEvents",
            options=apigateway.IntegrationOptions(
                credentials_role=iam.Role(
                    self,
                    "ApiGatewayInvokeEventBridgeRole",
                    assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
                    inline_policies={
                        "AllowEventBridgePutEvents": iam.PolicyDocument(
                            statements=[
                                iam.PolicyStatement(
                                    actions=["events:PutEvents"],
                                    resources=[refresh_sinch_token_event_bus.event_bus_arn]
                                )
                            ]
                        )
                    }
                ),
                integration_responses=[{
                    "statusCode": "200"
                }]
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

        resource = rest_api.root.add_resource('sinch')
        resource.add_method(
            "POST",
            integration=refresh_sinch_token_rule_integration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
            authorization_scopes=[f'{self.get_auth_server_name()}/{self.AUTH_SCOPE_REFRESH_SINCH_TOKEN}']
        ).add_method_response(status_code='200', response_models={"application/json": empty_model})

        refresh_sinch_token_rule.add_target(targets.LambdaFunction(self.refresh_sinch_token_lambda))
    
    def create_cognito_server(self) -> cognito.UserPool:
        user_pool = cognito.UserPool(
            self,
            'RefreshSinchTokenCognitoUserPool',
            self_sign_up_enabled=False,
            user_pool_name=self.get_auth_server_name()
        )
        user_pool.add_domain(
            'RefreshSinchTokenUserPoolDomain',
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=self.get_auth_server_name())
        )

        sms_scope = cognito.ResourceServerScope(
            scope_name=self.AUTH_SCOPE_REFRESH_SINCH_TOKEN,
            scope_description='refresh sinch token scope'
        )
        resource_server = user_pool.add_resource_server(
            'RefreshSinchTokenCognitoResourceServer',
            identifier=self.get_auth_server_name(),
            user_pool_resource_server_name=self.get_auth_server_name(),
            scopes=[sms_scope]
        )

        user_pool.add_client(
            'RefreshSinchTokenCognitoUserPoolClient',
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

    def module_name(self) -> str:
        return 'refresh-sinch-token'

    def code_location(self) -> str:
        return 'refresh_sinch_token'
    
    def create_vpc(self) -> ec2.Vpc:
        vpc = ec2.Vpc(
            self, 
            "RefreshSinchTokenVpc",
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
