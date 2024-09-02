#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk.random_system.random_system import RandomSystemStack
from cdk.common.execution_context import ExecutionContext


app = cdk.App()
execution_context = ExecutionContext(app)
random_system = RandomSystemStack(
    app,
    "RandomSystemStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)

app.synth()
