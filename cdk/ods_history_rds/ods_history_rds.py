from aws_cdk import (
    Stack,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_kms as kms,
)
from constructs import Construct
from cdk.common.execution_context import ExecutionContext


class ODSHistoryRdsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        self.execution_context: ExecutionContext = kwargs.pop("execution_context")
        super().__init__(scope, construct_id, **kwargs)
        self.db_instance =self.create_rds_instance()

    def create_rds_instance(self) -> rds.DatabaseInstance:
        kms_key_alias = kms.Alias.from_alias_name(
            self,
            self.execution_context.aws_kms.create_resource_id("imported-rds-alias"),
            "alias/aws/rds"
        )
        vpc = ec2.Vpc.from_vpc_attributes(
            self,
            f"omf-vpc-{self.execution_context.get_short_env()}-main-{self.region}-all",
            vpc_id=self.execution_context.env_properties['sms_vpc_id'],
            availability_zones=self.execution_context.env_properties['availability_zones'],
            private_subnet_ids=self.execution_context.env_properties['sms_subnet_ids']
            )
        local_sgs = self.execution_context.env_properties['rds_security_groups']
        security_groups = [ec2.SecurityGroup.from_security_group_id(
            self,
            f"RdsOdsImportedSg{i}",
            security_group_id=local_sgs[i]) for i in range(0, len(local_sgs) - 1)
        ]

        instance = rds.DatabaseInstance(
            self,
            "Instance",
            database_name="ods_db",
            engine=rds.DatabaseInstanceEngine.POSTGRES,
            storage_encryption_key=kms_key_alias,
            security_groups=security_groups,
            instance_type=ec2.InstanceType("t3.micro"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_filters=[ec2.SubnetFilter.by_ids(self.execution_context.env_properties['sms_subnet_ids'])]
            )
        )

        return instance
    
    def module_name(self) -> str:
        return 'ods-history-rds'