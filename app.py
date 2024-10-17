#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.common.execution_context import ExecutionContext
from cdk.sinch_proxy.sinch_proxy import SinchServiceStack

app = cdk.App()

# read environment specific properties
execution_context = ExecutionContext(app)
sinch_service = SinchServiceStack(
    app,
    "SinchServiceStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)


# Tags
execution_context.add_mandatory_tags(app)
app.synth()
