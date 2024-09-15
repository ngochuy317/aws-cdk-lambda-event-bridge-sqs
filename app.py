#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.ods.ods import ODSStack
from cdk.ods_history_rds.ods_history_rds import ODSHistoryRdsStack
from cdk.ods_history_class_mapper.ods_history_class_mapper import ODSHistoryClassMapperStack
from cdk.common.execution_context import ExecutionContext

app = cdk.App()

# read environment specific properties
execution_context = ExecutionContext(app)

# ods_history_rds = ODSHistoryRdsStack(
#     app,
#     "ODSHistoryRdsStack",
#     execution_context=execution_context,
#     env=execution_context.target_environment,
# )
ods_history_class_mapper = ODSHistoryClassMapperStack(
    app,
    "ODSHistoryClassMapperStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)
ods = ODSStack(
    app,
    "ODSStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
    history_class_mapper_lambda=ods_history_class_mapper.history_class_mapper_lambda,
)

# Tags
execution_context.add_mandatory_tags(app)
app.synth()
