from aws_cdk import (
    Duration,
    Stack,
    aws_events,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_events_targets as targets,
)
from constructs import Construct


class TimeZoneHoldQueueStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context = kwargs.pop("execution_context")
        # self.holidays_table = kwargs.pop("holidays_table")
        super().__init__(scope, construct_id, **kwargs)
        self.account_id = self.execution_context.env_properties['account_id']

        # For testing
        self.target_lambda_name = "test"

        # The code that defines your stack goes here
        self.controller_lambda_role = self.create_lambda_role(
            self.execution_context.aws_role.create_resource_name(self.module_name())
        )
        self.controller_lambda_function = self.create_lambda_function(
            self.execution_context.aws_lambda.create_resource_id(self.module_name()),
            self.execution_context.aws_lambda.create_resource_name(self.module_name()),
            "timezone_hold_queue.main.lambda_handler",
            role=self.controller_lambda_role,
            env_vars={
                "TARGET_LAMBDA_NAME": self.target_lambda_name,
                "REGION": self.region,
                "ACCOUNT_ID": self.account_id,
                "START_TIME_HOUR": "8",
                "START_TIME_MINUTE": "0",
                "END_TIME_HOUR": "20",
                "END_TIME_MINUTE": "30",
                "SAFETY_ZONE_START_HOUR": "14",
                "SAFETY_ZONE_START_MINUTE": "0",
                "SAFETY_ZONE_END_HOUR": "20",
                "SAFETY_ZONE_END_MINUTE": "30",
                # "TABLE_NAME": self.holidays_table.table_name
            }
        )


        self.event_bridge_rule = self.create_event_bridge_rule()
        self.event_bridge_rule.add_target(targets.LambdaFunction(self.controller_lambda_function))

    def module_name(self):
        return 'timezone-hold-queue'

    def code_location(self):
        return 'timezone_hold_queue'

    def create_lambda_function(
        self,
        id: str,
        lambda_function_name: str,
        handler: str,
        role: iam.Role = None,
        env_vars: dict = {},
    ) -> _lambda.Function:

        lambda_function = _lambda.Function(
            self,
            id,
            function_name=lambda_function_name,
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler=handler,
            environment=env_vars,
            runtime=_lambda.Runtime.PYTHON_3_9,
            role=role,
        )

        return lambda_function

    def create_event_bridge_rule(self) -> aws_events.Rule:
        rule = aws_events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_name(self.module_name()),
            description='Event Rule to trigger controller lambda function to control hold queue.',
            rule_name=self.execution_context.aws_event_rule.create_resource_name(self.module_name()),
            schedule=aws_events.Schedule.rate(Duration.minutes(1)),
        )
        return rule

    def create_lambda_role(self, role_name) -> iam.Role:
        lambda_role = iam.Role(
            self,
            role_name,
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ]
        )
        # self.holidays_table.grant_read_data(lambda_role)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:GetEventSourceMapping",
                    "lambda:ListEventSourceMappings",
                ],
                resources=["*"]
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:UpdateEventSourceMapping",
                ],
                resources=["*"],
                condition={
                    "StringEquals": {
                        "lambda:FunctionArn": f"arn:aws:lambda:{self.region}:{self.account_id}:function:{self.target_lambda_name}"
                    }
                }
            )
        )
        return lambda_role