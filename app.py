#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk.message_submit_callbacks.message_submit_callbacks import MessageSubmitCallbacksStack
from cdk.common.execution_context import ExecutionContext


app = cdk.App()
execution_context = ExecutionContext(app)
message_submit_callback = MessageSubmitCallbacksStack(
    app,
    "MessageSubmitCallbacksStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)

app.synth()
