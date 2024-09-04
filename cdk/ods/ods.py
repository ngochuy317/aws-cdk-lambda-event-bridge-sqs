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
    ENV_ODS_DB_CLUSTER_ARN,
    ENV_ODS_DB_SECRET_ARN,
    ENV_ODS_DB_NAME,
    ENV_ODS_OUTPUT_QUEUE_URL
)

class ODSStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.history_message_submit_buffer_queue = self.create_fifo_queue("history-message-submit-buffer")
        self.history_message_submit_buffer_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id(f"{self.module_name()}-history-message-submit-buffer"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-history-message-submit-buffer"),
            description="Event Rule to trigger history message submit buffer queue",
            schedule=events.Schedule.rate(Duration.minutes(1)),
        )
        self.history_message_submit_buffer_rule.add_target(
            targets.SqsQueue(
                self.history_message_submit_buffer_queue,
                message=events.RuleTargetInput.from_event_path('$.detail'),
                message_group_id="MyMessageGroupId" 
            )
        )

        self.history_message_income_buffer_queue = self.create_fifo_queue("history-message-income-buffer")
        self.history_message_income_buffer_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id(f"{self.module_name()}-history-message-income-buffer"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-history-message-income-buffer"),
            description="Event Rule to trigger history message income buffer queue",
            schedule=events.Schedule.rate(Duration.minutes(1)),
        )
        self.history_message_income_buffer_rule.add_target(
            targets.SqsQueue(
                self.history_message_income_buffer_queue,
                message=events.RuleTargetInput.from_event_path('$.detail'),
                message_group_id="MyMessageGroupId" 
            )
        )

        self.history_message_delivery_report_buffer_queue = self.create_fifo_queue("history-message-delivery-report-buffer")
        self.history_message_delivery_report_buffer_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id(f"{self.module_name()}-history-msg-delivery-report"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-history-msg-delivery-report"),
            description="Event Rule to trigger history message delivery report buffer queue",
            schedule=events.Schedule.rate(Duration.minutes(1)),
        )
        self.history_message_delivery_report_buffer_rule.add_target(
            targets.SqsQueue(
                self.history_message_delivery_report_buffer_queue,
                message=events.RuleTargetInput.from_event_path('$.detail'),
                message_group_id="MyMessageGroupId" 
            )
        )

        self.history_class_buffer_queue = self.create_fifo_queue("history-class-buffer")

        # self.vpc = ec2.Vpc(self, f"{self.module_name()}-vpc")

        # engine_version = rds.AuroraPostgresEngineVersion.VER_13_4
        # self.cluster = rds.ServerlessCluster(
        #     self,
        #     self.execution_context.base.create_base_resource_name("cluster", "rds"),
        #     engine=rds.DatabaseClusterEngine.aurora_postgres(version=engine_version),
        #     vpc=self.vpc,
        #     enable_data_api=True
        # )

        self.ods_history_processor_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-history-processor-handler"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-history-processor-handler"),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="ods.ods_history_processor_lambda.lambda_handler",
            environment={
                # ENV_ODS_DB_CLUSTER_ARN: self.cluster.cluster_arn,
                # ENV_ODS_DB_SECRET_ARN: self.cluster.secret.secret_arn,
                # ENV_ODS_DB_NAME: "postgres",
                ENV_ODS_OUTPUT_QUEUE_URL: self.history_class_buffer_queue.queue_url
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
            # vpc=self.vpc,
        )

        # self.cluster.secret.grant_read(self.ods_history_processor_lambda)
        # self.ods_history_processor_lambda.add_to_role_policy(
        #     iam.PolicyStatement(
        #         actions=["rds-data:ExecuteStatement"],
        #         resources=[self.cluster.cluster_arn]
        #     )
        # )

        self.ods_history_processor_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.history_message_submit_buffer_queue))

        self.history_class_mapper_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-history-class-mapper-handler"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-history-class-mapper-handler"),
            code=self.execution_context.aws_lambda.get_local_code(self.code_location()),
            handler="ods.class_mapper_lambda.lambda_handler",
            environment={
                # ENV_ODS_DB_CLUSTER_ARN: self.cluster.cluster_arn,
                # ENV_ODS_DB_SECRET_ARN: self.cluster.secret.secret_arn,
                ENV_ODS_DB_NAME: "postgres",
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
            # vpc=self.vpc,
        )

        self.history_class_mapper_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.history_class_buffer_queue))

        self.history_class_buffer_queue.grant_send_messages(self.ods_history_processor_lambda)
        # self.cluster.secret.grant_read(self.history_class_mapper_lambda)
        # self.history_class_mapper_lambda.add_to_role_policy(
        #     iam.PolicyStatement(
        #         actions=["rds-data:ExecuteStatement"],
        #         resources=[self.cluster.cluster_arn]
        #     )
        # )

        # init data for db
        # self.init_db()

    def module_name(self):
        return 'ods'

    def code_location(self):
        return 'ods'

    def create_fifo_queue(self, queue_name) -> sqs.Queue:
        queue, _ = (
            self.execution_context.aws_sqs.create_fifo_queue(
                f"{self.module_name()}-{queue_name}",
                self,
                visibility_timeout=Duration.seconds(60)
            )
        )
        return queue

    def create_rds_instance(self):
        self.vpc = ec2.Vpc.from_vpc_attributes(
            self,
            f"{self.module_name()}-vpc-{self.execution_context.get_short_env()}-main-{self.region}-all"
        )

    def init_db(self):
        "init some data for testing"

        init_db_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-init-db"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-init-db"),
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="ods.init_db.handler",
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
