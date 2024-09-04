#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk.ods.ods import ODSStack
from cdk.common.execution_context import ExecutionContext


app = cdk.App()
execution_context = ExecutionContext(app)
ods = ODSStack(
    app,
    "ODSStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)

app.synth()
