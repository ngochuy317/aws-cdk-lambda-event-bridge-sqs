import aws_cdk as cdk
from aws_cdk.aws_sqs import DeduplicationScope
import subprocess
import os
import jsii


@jsii.implements(cdk.ILocalBundling)
class LocalBundle:
    def __init__(self, module_name, is_pip_install, is_include_common):
        self.module_name = module_name
        self.is_pip_install = is_pip_install
        self.is_include_common = is_include_common

    def try_bundle(self, output_dir, options):
        try:
            subprocess.run(["pip3", "--version"])
        except Exception as err:
            return False

        cwd = os.getcwd()
        if self.is_pip_install:
            subprocess.run(
                ["pip3", "install", "-r", os.path.join(cwd, f"apps/{self.module_name}/requirements.txt"), "-t",
                 output_dir])

        subprocess.run(["cp", "-r", os.path.join(cwd, f"apps/{self.module_name}"), output_dir])

        if self.is_include_common:
            subprocess.run(["cp", "-r", os.path.join(cwd, "apps/common"), output_dir])

        return True


class ExecutionContext:
    def __init__(self, app):
        self.target_env = app.node.try_get_context("env") or "dev"
        self.env_properties = app.node.try_get_context("environments")[self.target_env]
        self.target_environment = cdk.Environment(account=self.env_properties['account_id'],
                                                  region=self.env_properties['region'])
        self.base = BaseAwsResource(
            short_env=self.get_short_env(), project=self.get_project().lower(), short_region=self.get_short_region()
        )
        self.aws_sqs = AwsSqsResource(self.base)
        self.aws_lambda = AwsLambdaResource(self.base)
        self.aws_ssm = AwsSsmResource(self.base)
        self.aws_dynamo_db = AwsDynamoDbResource(self.base)
        self.aws_iam = AwsIamResource(self.base)
        self.aws_role = AwsRoleResource(self.base)
        self.aws_api_gateway = AwsApiGatewayResource(self.base)
        self.aws_event_bus = AwsEventBusResource(self.base)
        self.aws_event_rule = AwsEventRuleResource(self.base)
        self.aws_glue = AwsGlueJobResource(self.base)
        self.aws_kms = AwsKmsResource(self.base)

    def get_short_env(self):
        return self.env_properties["short_env"]

    def get_project(self):
        return self.env_properties["project"]

    def get_short_region(self):
        return self.env_properties["short_region"]

    def get_artifacts_bucket(self, stack):
        return self.get_bucket_by_fn_arn(f"{self.get_project().lower()}-artifacts-arn", stack)

    def get_cld_artifacts_bucket(self, stack):
        return self.get_bucket_by_fn_arn("cld360-artifacts-arn", stack)

    def get_bucket_by_fn_arn(self, fn_arn, stack):
        return cdk.aws_s3.Bucket.from_bucket_arn(stack, fn_arn.title().replace('-', ''),
                                                 bucket_arn=self.get_fn_value(fn_arn))

    def get_acs_host(self):
        return self.env_properties["acs_host"]

    def get_profile_host(self):
        return self.env_properties["profile_host"]

    def get_hosted_zone_name(self):
        return self.env_properties["hosted_zone_name"]

    def get_hosted_zone_id(self):
        return self.env_properties["hosted_zone_id"]

    def get_acm_cert_arn(self):
        return self.env_properties["acm_cert_arn"]

    def is_non_prod(self):
        return self.get_short_env() != 'prod'

    def add_mandatory_tags(self, app):
        cdk.Tags.of(app).add("Environment", self.env_properties["environment"])
        cdk.Tags.of(app).add("Env", self.get_short_env())
        cdk.Tags.of(app).add("Project", self.env_properties["project"])
        cdk.Tags.of(app).add("Sub_Project", self.env_properties["sub_project"])

    @staticmethod
    def get_fn_value(fn_key):
        return cdk.Fn.import_value(fn_key)


class BaseAwsResource:
    def __init__(self, short_env, short_region, project):
        self.short_env = short_env
        self.short_region = short_region
        self.project = project

    def create_base_resource_id(self, aws_service_name, resource_name):
        return f"{self.project.capitalize()}{aws_service_name.capitalize()}{self.short_env.capitalize()}{resource_name.title().replace('-', '')}{self.short_region.capitalize()}"

    def create_base_resource_name(self, aws_service_name, resource_name, suffix=""):
        return f"{self.project}-{aws_service_name}-{self.short_env}-{resource_name}-{self.short_region}-all{suffix}"


class SpecificAwsResource:
    def __init__(self, aws_service_name, base_resource):
        self.base_resource = base_resource
        self.aws_service_name = aws_service_name

    def create_resource_id(self, resource_name):
        return self.base_resource.create_base_resource_id(self.aws_service_name, resource_name)

    def create_resource_name(self, resource_name, suffix=""):
        return self.base_resource.create_base_resource_name(self.aws_service_name, resource_name, suffix)

    def create_resource_name_service(self, resource_name, service_name, suffix=""):
        return self.base_resource.create_base_resource_name(service_name, resource_name, suffix)

class AwsSqsResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("sqs", base_resource)

    def create_sqs_dlq_name(self, queue_name, suffix=""):
        return self.create_resource_name(f"{queue_name}-dlq", suffix)

    def create_sqs_dlq_id(self, queue_name):
        return self.create_resource_id(f"{queue_name}-dlq")

    def create_standard_queue(self, queue_name, stack, visibility_timeout=None):
        dead_letter_queue = cdk.aws_sqs.DeadLetterQueue(
            max_receive_count=4,
            queue=cdk.aws_sqs.Queue(stack, self.create_sqs_dlq_id(queue_name),
                                    queue_name=self.create_sqs_dlq_name(queue_name))
        )
        output_queue = cdk.aws_sqs.Queue(stack, self.create_resource_id(queue_name),
                                         queue_name=self.create_resource_name(queue_name),
                                         dead_letter_queue=dead_letter_queue,
                                         visibility_timeout=visibility_timeout)

        stack.export_value(output_queue.queue_arn)

        return output_queue, dead_letter_queue

    def create_fifo_queue(self, queue_name, stack, visibility_timeout=None, encryption=None, master_key=None):
        dead_letter_queue = cdk.aws_sqs.DeadLetterQueue(
            max_receive_count=4,
            queue=cdk.aws_sqs.Queue(stack, self.create_sqs_dlq_id(queue_name),
                                    queue_name=self.create_sqs_dlq_name(queue_name, ".fifo"),
                                    fifo=True)
        )
        output_queue = cdk.aws_sqs.Queue(stack, self.create_resource_id(queue_name),
                                         queue_name=self.create_resource_name(queue_name, ".fifo"),
                                         dead_letter_queue=dead_letter_queue,
                                         fifo=True,
                                         content_based_deduplication=True,
                                         deduplication_scope=DeduplicationScope.QUEUE,
                                         visibility_timeout=visibility_timeout,
                                         encryption=encryption,
                                         encryption_master_key=master_key)

        stack.export_value(output_queue.queue_arn)

        return output_queue, dead_letter_queue

    def create_single_queue(self, name, stack):
        single_queue = cdk.aws_sqs.Queue(stack, self.create_resource_id(name),
                                         queue_name=self.create_resource_name(name))
        # stack.export_value(single_queue.queue_arn, name=f"{single_queue}-arn")
        return single_queue


class AwsLambdaResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("lambda", base_resource)

    @staticmethod
    def get_local_code(module_name, is_pip_install=False, is_include_common=True):
        return cdk.aws_lambda.Code.from_asset(f"./apps/{module_name}", bundling=cdk.BundlingOptions(
            image=cdk.aws_lambda.Runtime.PYTHON_3_9.bundling_image,
            command=[],
            local=LocalBundle(module_name, is_pip_install, is_include_common),
        ))


class AwsDynamoDbResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("dynamo-db", base_resource)

    def create_table(self, scope, table_name, partition_key, sort_key=None, time_to_live_attribute=None):
        args = {
            "scope": scope,
            "id": self.create_resource_id(table_name),
            "table_name": self.create_resource_name(table_name),
            "partition_key": cdk.aws_dynamodb.Attribute(
                name=partition_key,
                type=cdk.aws_dynamodb.AttributeType.STRING
            ),
            "billing_mode": cdk.aws_dynamodb.BillingMode.PAY_PER_REQUEST
        }

        if sort_key:
            args['sort_key'] = cdk.aws_dynamodb.Attribute(
                name=sort_key, type=cdk.aws_dynamodb.AttributeType.STRING
            )

        if time_to_live_attribute:
            args['time_to_live_attribute'] = time_to_live_attribute

        return cdk.aws_dynamodb.Table(**args)

    def create_table_for_lambda(self, env_var_table_name, lambda_handler, scope, table_name, partition_key,
                                sort_key=None, time_to_live_attribute=None, write_access=None):
        dynamo_table = self.create_table(
            scope, table_name, partition_key, sort_key, time_to_live_attribute
        )

        dynamo_table.grant_read_data(lambda_handler)
        if write_access:
            dynamo_table.grant_write_data(lambda_handler)

        lambda_handler.add_environment(env_var_table_name, dynamo_table.table_name)
        lambda_handler.add_environment(f"{self.format_lambda_env_var(table_name)}_PARTITION_KEY", partition_key)

        if sort_key:
            lambda_handler.add_environment(f"{self.format_lambda_env_var(table_name)}_SORT_KEY", sort_key)

        return dynamo_table

    @staticmethod
    def format_lambda_env_var(value):
        return value.upper().replace("-", "_")


class AwsIamResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("iam", base_resource)


class AwsRoleResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("role", base_resource)


class AwsSsmResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("ssm", base_resource)

    def create_resource_name(self, resource_name, suffix=""):
        return f"/{self.base_resource.short_env}/{resource_name}"

    def create_ssm_parameter_id(self, parameter_name):
        return self.create_resource_id(parameter_name)

    def create_ssm_parameter_placeholder(self, stack, parameter_name, description):
        return cdk.aws_ssm.StringParameter(stack, self.create_ssm_parameter_id(parameter_name),
                                           allowed_pattern=".*", description=description,
                                           parameter_name=self.create_resource_name(parameter_name),
                                           string_value="PLACEHOLDER")


class AwsApiGatewayResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("api-gateway", base_resource)


class AwsEventBusResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("event-bus", base_resource)


class AwsEventRuleResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("event-rule", base_resource)


class AwsGlueJobResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("glue", base_resource)


class AwsKmsResource(SpecificAwsResource):
    def __init__(self, base_resource):
        super().__init__("kms", base_resource)
