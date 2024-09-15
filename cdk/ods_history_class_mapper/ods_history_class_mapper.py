from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext


class ODSHistoryClassMapperStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.history_class_mapper_lambda = _lambda.Function(
            self,
            self.execution_context.aws_lambda.create_resource_id(f"{self.module_name()}-handler"),
            function_name=self.execution_context.aws_lambda.create_resource_name(f"{self.module_name()}-handler"),
            code=self.execution_context.aws_lambda.get_local_code("history_class_mapper_lambda"),
            handler="history_class_mapper_lambda.history_class_mapper_lambda.lambda_handler",
            environment={},
            runtime=_lambda.Runtime.PYTHON_3_9,
        )
    
    def module_name(self) -> str:
        return 'ods-history-class-mapper'