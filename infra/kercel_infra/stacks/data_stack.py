from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from kercel_infra.config import KercelStageConfig, get_stage_config
from kercel_infra.constructs.database import DatabaseConstruct


class DataStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        vpc: ec2.IVpc,
        redis_security_group: ec2.ISecurityGroup,
        config: KercelStageConfig | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stage_config = config or get_stage_config(stage)

        database = DatabaseConstruct(
            self,
            "Database",
            stage=stage,
            config=stage_config,
            vpc=vpc,
            redis_security_group=redis_security_group,
        )

        self.user_table = database.user_table
        self.project_table = database.project_table
        self.history_table = database.history_table
        self.deploy_act_table = database.deploy_act_table
        self.ws_connections_table = database.ws_connections_table
        self.artifacts_bucket = database.artifacts_bucket
        self.output_bucket = database.output_bucket
        self.deployment_queue = database.deployment_queue
        self.deployment_dlq = database.deployment_dlq
        self.redis_cluster = database.redis_cluster
        self.distribution = database.distribution
