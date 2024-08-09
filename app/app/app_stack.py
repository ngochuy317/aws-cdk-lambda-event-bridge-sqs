from aws_cdk import (
    Duration,
    Stack,
    aws_events as events,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_sqs as sqs,
    aws_events_targets as targets,
    aws_lambda_event_sources as lambda_event_sources,
)
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from constructs import Construct


class AppStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        # self.hold_queue = self.create_sqs_queue("HoldQueue", None)

        # list queue for testing
        self.queue1 = self.create_sqs_queue("Queue1", "Queue1-est.fifo", set_access_policy=True)
        self.queue2 = self.create_sqs_queue("Queue2", "Queue2-pdt.fifo", set_access_policy=True)
        self.queue3 = self.create_sqs_queue("Queue3", "Queue3-mst.fifo")

        self.controller_lambda_role = self.create_lambda_role("LambdaExecutionRole")
        self.controller_lambda_function = self.create_lambda_function(
            "Controller",
            "cdk/aws_lambda",
            "controller_lambda.py",
            "lambda_handler",
            role=self.controller_lambda_role,
            env_vars={
                "QUEUE_NAMES": f'{self.queue1.queue_name},{self.queue2.queue_name},{self.queue3.queue_name}',
                "REGION": self.execution_context.env_properties['region'],
                "ACCOUNT_ID": self.execution_context.env_properties['account_id']
            }
        )

        self.controller_lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SetQueueAttributes",
                    "sqs:GetQueueAttributes",
                ],
                resources=[self.queue1.queue_arn, self.queue2.queue_arn, self.queue3.queue_arn]
            )
        )

        self.event_bridge_rule = self.create_event_bridge()
        self.event_bridge_rule.add_target(targets.LambdaFunction(self.controller_lambda_function))

    def create_sqs_queue(self, id: str, queue_name: str, set_access_policy=False) -> sqs.Queue:
        queue = sqs.Queue(self, id, queue_name=queue_name, content_based_deduplication=True)
        if set_access_policy:
            policy_statement = iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:SendMessage"],
                resources=[queue.queue_arn]
            )
            queue.add_to_resource_policy(policy_statement)
        return queue

    def create_lambda_function(
        self,
        lambda_function_name: str,
        entry: str,
        index: str,
        handler: str,
        role: iam.Role = None,
        env_vars: dict = {},
    ) -> PythonFunction:

        lambda_function = PythonFunction(
            self,
            lambda_function_name,
            runtime=_lambda.Runtime.PYTHON_3_11,
            entry=entry,
            index=index,
            handler=handler,
            environment=env_vars,
            role=role,
        )

        return lambda_function

    def create_event_bridge(self) -> events.Rule:
        rule = events.Rule(
            self,
            'Rule',
            # schedule=events.Schedule.rate(Duration.minutes(10)),
            schedule=events.Schedule.rate(Duration.minutes(1)),
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
        return lambda_role
