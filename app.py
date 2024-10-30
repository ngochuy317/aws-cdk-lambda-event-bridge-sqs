#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.common.execution_context import ExecutionContext
from cdk.sinch_proxy.sinch_proxy import SinchServiceStack
from cdk.sms_sinch_request_log.sms_sinch_request_log import SmsSinchRequestLogStack
from cdk.sinch_rest_api.sinch_rest_api import SinchRestApiStack
from cdk.sinch_incoming_messages_webhook.sinch_incoming_messages_webhook import SinchIncomingMessagesWebhookStack
from cdk.sinch_sms_response_event.sinch_sms_response_event import SinchSmsResponseEvent
from cdk.sinch_message_delivery_webhook.sinch_message_delivery_webhook import SinchMessageDeliveryWebhook

app = cdk.App()

# read environment specific properties
execution_context = ExecutionContext(app)
sinch_sms_response_event = SinchSmsResponseEvent(
    app,
    "SinchSmsResponseEvent",
    execution_context=execution_context,
    env=execution_context.target_environment,
)
sms_sinch_request_log = SmsSinchRequestLogStack(
    app,
    "SmsSinchRequestLogStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
)
sinch_incoming_messages_webhook = SinchIncomingMessagesWebhookStack(
    app,
    "SinchIncomingMessagesWebhookStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
    sinch_sms_response_event_bus=sinch_sms_response_event.sinch_sms_response_event_bus,
)
sinch_message_delivery_webhook = SinchMessageDeliveryWebhook(
    app,
    "SinchMessageDeliveryWebhook",
    execution_context=execution_context,
    env=execution_context.target_environment,
    sinch_sms_response_event_bus=sinch_sms_response_event.sinch_sms_response_event_bus,
    sms_sinch_request_log_table=sms_sinch_request_log.sms_sinch_request_log_table,
)
sinch_service = SinchServiceStack(
    app,
    "SinchServiceStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
    sms_sinch_request_log_table=sms_sinch_request_log.sms_sinch_request_log_table,
)
sinch_rest_api = SinchRestApiStack(
    app,
    "SinchRestApiStack",
    execution_context=execution_context,
    env=execution_context.target_environment,
    sinch_proxy_buffer_queue=sinch_service.sinch_proxy_buffer_queue,
    sinch_incoming_messages_webhook_lambda=sinch_incoming_messages_webhook.sinch_incoming_messages_webhook_lambda,
    sinch_message_webhook_buffer_queue=sinch_message_delivery_webhook.sinch_message_webhook_buffer_queue,
)


# Tags
execution_context.add_mandatory_tags(app)
app.synth()