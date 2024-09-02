from aws_cdk import (
    Duration,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_iam as iam,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext
from apps.common.constants import (
    ENV_RANDOM_SYSTEM_DB_CLUSTER_ARN,
    ENV_RANDOM_SYSTEM_DB_SECRET_ARN,
    ENV_RANDOM_SYSTEM_DB_NAME,
    ENV_RANDOM_SYSTEM_OUTPUT_QUEUE_URL
)

class RandomSystemStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.callback_message_buffer_queue = self.create_fifo_queue("callback-message-buffer")
        self.transform_message_buffer_queue = self.create_fifo_queue("transform-message-buffer")

        self.vpc = ec2.Vpc(self, f"{self.module_name()}-vpc")

        engine_version = rds.AuroraPostgresEngineVersion.VER_13_4
        self.cluster = rds.ServerlessCluster(
            self,
            self.execution_context.base.create_base_resource_name("cluster", "rds"),
            engine=rds.DatabaseClusterEngine.aurora_postgres(version=engine_version),
            vpc=self.vpc,
            enable_data_api=True
        )

        self.ods_history_processor_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-history-processor"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-history-processor"),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="random_system.ods_history_processor_lambda.lambda_handler",
            environment={
                ENV_RANDOM_SYSTEM_DB_CLUSTER_ARN: self.cluster.cluster_arn,
                ENV_RANDOM_SYSTEM_DB_SECRET_ARN: self.cluster.secret.secret_arn,
                ENV_RANDOM_SYSTEM_DB_NAME: "postgres",
                ENV_RANDOM_SYSTEM_OUTPUT_QUEUE_URL: self.transform_message_buffer_queue.queue_url
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
            vpc=self.vpc,
        )

        self.cluster.secret.grant_read(self.ods_history_processor_lambda)
        self.ods_history_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rds-data:ExecuteStatement"],
                resources=[self.cluster.cluster_arn]
            )
        )

        self.ods_history_processor_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.callback_message_buffer_queue))

        self.class_mapper_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-class-mapper"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-class-mapper"),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="random_system.class_mapper_lambda.lambda_handler",
            environment={
                ENV_RANDOM_SYSTEM_DB_CLUSTER_ARN: self.cluster.cluster_arn,
                ENV_RANDOM_SYSTEM_DB_SECRET_ARN: self.cluster.secret.secret_arn,
                ENV_RANDOM_SYSTEM_DB_NAME: "postgres",
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
            vpc=self.vpc,
        )

        self.class_mapper_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.transform_message_buffer_queue))

        self.transform_message_buffer_queue.grant_send_messages(self.ods_history_processor_lambda)
        self.cluster.secret.grant_read(self.class_mapper_lambda)
        self.class_mapper_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rds-data:ExecuteStatement"],
                resources=[self.cluster.cluster_arn]
            )
        )

        self.history_rule = self.create_event_bridge_rule("history-rule", "Event Rule to trigger callback message queue")

        self.history_rule.add_target(
            targets.SqsQueue(
                self.callback_message_buffer_queue,
                message=events.RuleTargetInput.from_event_path('$.detail'),
                message_group_id="MyMessageGroupId" 
            )
        )

        # Output the database endpoint
        # self.db_endpoint_output = self.db_instance.db_instance_endpoint_address


        # init data for db
        self.init_db()

    def module_name(self):
        return 'random-system'

    def code_location(self):
        return 'random_system'

    def create_fifo_queue(self, queue_name) -> sqs.Queue:
        queue, _ = (
            self.execution_context.aws_sqs.create_fifo_queue(
                f"{self.module_name()}-{queue_name}",
                self,
                visibility_timeout=Duration.seconds(60)
            )
        )
        return queue

    def create_event_bridge_rule(self, name: str, description: str) -> events.Rule:
        rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-{name}"),
            description=description,
            rule_name=self.execution_context.aws_event_rule.create_resource_name(self.module_name()),
            schedule=events.Schedule.rate(Duration.minutes(1)),
        )
        return rule

    def init_db(self):
        "init some data for testing"

        init_db_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-init-db"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-init-db"),
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="random_system.init_db.handler",
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            timeout=Duration.minutes(5),
            environment={
                "DB_CLUSTER_ARN": self.cluster.cluster_arn,
                "DB_SECRET_ARN": self.cluster.secret.secret_arn,
                "DB_NAME": "postgres"
            },
            vpc=self.vpc,
        )

        self.cluster.secret.grant_read(init_db_lambda)
        init_db_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rds-data:ExecuteStatement"],
                resources=[self.cluster.cluster_arn]
            )
        )

        # Create EventBridge Rule to trigger init_db_lambda after stack deployment
        init_db_rule = events.Rule(
            self,
            "InitDbRule",
            schedule=events.Schedule.rate(Duration.minutes(1))
        )
        init_db_rule.add_target(targets.LambdaFunction(init_db_lambda))
