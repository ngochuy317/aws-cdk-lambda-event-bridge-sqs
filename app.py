#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.common.execution_context import ExecutionContext
from cdk.sms_delegator.sms_delegator import SMSDelegatorStack


app = cdk.App()

# read environment specific properties
execution_context = ExecutionContext(app)
sms_delegator_stack = SMSDelegatorStack(
    app,
    "SMSDelegatorStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)



# Tags
execution_context.add_mandatory_tags(app)
app.synth()