#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.common.execution_context import ExecutionContext
from cdk.refresh_sinch_token.refresh_sinch_token import RefreshSinchTokenStack

app = cdk.App()

# read environment specific properties
execution_context = ExecutionContext(app)
refresh_sinch_token = RefreshSinchTokenStack(
    app,
    "RefreshSinchTokenStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)


# Tags
execution_context.add_mandatory_tags(app)
app.synth()
