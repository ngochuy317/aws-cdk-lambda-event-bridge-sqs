from aws_cdk import (
    Duration,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext

HISTORY_MSG_NAMES = ["history-msg-submit-buffer", "history-msg-income-buffer", "history-msg-delivery-rp-buffer"]


class ODSStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, history_class_mapper_lambda: _lambda.Function, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        self.history_class_mapper_lambda  = history_class_mapper_lambda
        super().__init__(scope, construct_id, **kwargs)

        self.history_class_buffer_queue, _ = self.execution_context.aws_sqs.create_standard_queue(
            f"{self.module_name()}-history-class-buffer",
            self,
            visibility_timeout=Duration.seconds(60)
        )
        self.history_class_mapper_lambda.add_event_source(lambda_event_sources.SqsEventSource(self.history_class_buffer_queue))


        self.ods_history_processor_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-history-processor-handler"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-history-processor-handler"),
            code=self.execution_context.aws_lambda.get_local_code("ods_history_processor_lambda"),
            handler="ods_history_processor_lambda.ods_history_processor_lambda.lambda_handler",
            environment={
                "ODS_TO_CLASS_QUEUE_URL": self.history_class_buffer_queue.queue_url
            },
            runtime=_lambda.Runtime.PYTHON_3_9,
        )
        self.history_class_buffer_queue.grant_send_messages(self.ods_history_processor_lambda)

        event_bus = events.EventBus(
            self,
            self.execution_context.aws_event_bus.create_resource_id(self.module_name()),
            event_bus_name=self.execution_context.aws_event_bus.create_resource_name(self.module_name()),
        )
        for name in HISTORY_MSG_NAMES:
            queue, _ = self.execution_context.aws_sqs.create_standard_queue(
                f"{self.module_name()}-{name}",
                self,
                visibility_timeout=Duration.seconds(60)
            )
            queue.grant_consume_messages(self.history_class_mapper_lambda)
            self.ods_history_processor_lambda.add_event_source(lambda_event_sources.SqsEventSource(queue))

            rule = events.Rule(
                self,
                self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-{name}"),
                description=self.event_bus_description(name),
                rule_name=self.execution_context.aws_event_rule.create_resource_name(f"{self.module_name()}-{name}"),
                event_pattern=events.EventPattern(
                    source=["SINCH"],
                ),
                event_bus=event_bus,
            )

            rule.add_target(
                targets.SqsQueue(
                    queue,
                    message=events.RuleTargetInput.from_event_path('$.detail'),
                )
            )

    def event_bus_description(self, name: str) -> str:
        return "Event Rule to trigger " + name.replace('-', ' ') + " queue"

    def event_bus_action(self) -> list:
        return [{'prefix': 'dummy'}]

    def module_name(self) -> str:
        return 'ods'
