from aws_cdk import (
    Stack,
    aws_events as events,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext

class SinchSmsResponseEvent(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)

        self.loan_short_codes = self.execution_context.env_properties['loan_short_codes']
        self.opt_in_expression = [{
            "real_body": [{"equals-ignore-case": key_word}]} for key_word in self.execution_context.env_properties['opt_in_key_words'
        ]]
        self.opt_out_expression = [{
            "real_body": [{"equals-ignore-case": key_word}]} for key_word in self.execution_context.env_properties['opt_out_key_words'
        ]]

        self.sinch_sms_response_event_bus = events.EventBus(
            self,
            self.execution_context.aws_event_bus.create_resource_id("sinch-sms-response"),
            event_bus_name=self.execution_context.aws_event_bus.create_resource_name("sinch-sms-response"),
        )

        self.create_event_rule()

    def create_event_rule(self) -> None:
        self.sinch_sms_response_event_archive = events.CfnArchive(
            self,
            self.execution_context.aws_event_rule.create_resource_id("sms-resp-archive"),
            archive_name=self.execution_context.aws_event_rule.create_resource_name("sms-resp-archive"),
            source_arn=self.sinch_sms_response_event_bus.event_bus_arn,
            description="Archive for Sinch SMS response events"
        )

        self.loans_sms_response_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id("loans-sms-response"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name("loans-sms-response"),
            description="SMS response to Loans short code.",
            enabled=True,
            event_bus=self.sinch_sms_response_event_bus,
            event_pattern={
                "detail": {
                    "real_to": [
                        self.loan_short_codes["loans"],
                        self.loan_short_codes["loans_servicing"],
                        self.loan_short_codes["loans_promotions"],
                        self.loan_short_codes["loans_collections"]
                    ]
                }
            }
        )

        self.optout_all_sms_response_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id("optout-all-sms-response"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name("optout-all-sms-response"),
            description="SMS response with Optout keywords to all short codes.",
            enabled=True,
            event_bus=self.sinch_sms_response_event_bus,
            event_pattern={
                "detail": {
                    "$or": self.opt_out_expression
                }
            }
        )

        self.optin_all_sms_response_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id("optin-all-sms-response"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name("optin-all-sms-response"),
            description="SMS response with Optin keywords to all short codes.",
            enabled=True,
            event_bus=self.sinch_sms_response_event_bus,
            event_pattern={
                "detail": {
                    "$or": self.opt_in_expression
                }
            }
        )

        self.cards_message_center_email_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id("cards-message-center-email"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name("cards-message-center-email"),
            description="Cards message center email event.",
            enabled=True,
            event_bus=self.sinch_sms_response_event_bus,
            event_pattern={
                "detail": {
                    "campaign_group": ["cards_auth_msg_center"]
                }
            }
        )

        self.sms_delivery_receipt_to_contact_pro_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id("sms-delivery-receipt-to-contact-pro"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name("sms-delivery-receipt-to-contact-pro"),
            description="SMS delivery receipt to Contact Pro",
            enabled=True,
            event_bus=self.sinch_sms_response_event_bus,
            event_pattern={
                "detail": {
                    "event_status": ["DELIVERED"],
                    "acs_data": {
                        "$or": [
                            {
                                "unique_request_id": [{"prefix": "s2_"}]
                            },
                            {
                                "unique_request_id": [{"prefix": "s1_"}]
                            }
                        ],
                        "short_code": [self.loan_short_codes["loans_new_collections"]]
                    }
                }
            }
        )

        self.sms_delivery_receipt_to_mule_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id("sms-delivery-receipt-to-mule"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name("sms-delivery-receipt-to-mule"),
            description="SMS delivery receipt to Mule",
            enabled=True,
            event_bus=self.sinch_sms_response_event_bus,
            event_pattern={
                "detail": {
                    "event_status": ["DELIVERED"],
                    "acs_data": {
                        "unique_request_id": [{"prefix": "s2_"}],
                        "delivery_id": [{"anything-but": ["LOANS S1"]}],
                        "short_code": [self.loan_short_codes["loans_new_collections"]]
                    }
                }
            }
        )

        self.sms_response_to_new_account_rule = events.Rule(
            self,
            self.execution_context.aws_event_rule.create_resource_id("sms-response-to-new-account"),
            rule_name=self.execution_context.aws_event_rule.create_resource_name("sms-response-to-new-account"),
            description="SMS response event to new account.",
            enabled=True,
            event_bus=self.sinch_sms_response_event_bus,
            event_pattern={
                "source": ["SINCH"],
                "detail_type": ["SMS_RESPONSE", "original_income_message", "original_delivery_receipt"]
            }
        )

        for config_name, config in self.execution_context.env_properties['sms_message_configuration'].items():
            if len(config["key_words_expression"]) > 1:
                event_pattern = {
                    "detail": {
                        "real_to": config["short_codes"],
                        "$or": config["key_words_expression"]
                    }
                }
            else:
                event_pattern = {
                    "detail": {
                        "real_to": config["short_codes"],
                        "real_body": config["key_words_expression"][0]["real_body"]
                    }
                }

            loan_short_codes = [
                self.execution_context.env_properties["loan_short_codes"][short_code] for short_code in config['short_codes']
            ]
            rule = events.Rule(
                self,
                self.execution_context.aws_event_rule.create_resource_id(config_name),
                rule_name=self.execution_context.aws_event_rule.create_resource_name(config_name),
                description=f"SMS response with {config_name} to {loan_short_codes} short code.",
                enabled=config["enabled"],
                event_bus=self.sinch_sms_response_event_bus,
                event_pattern=event_pattern
            )