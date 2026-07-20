from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from kercel_infra.config import KercelStageConfig
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
        # BUG-18 FIX: The original signature had `config: KercelStageConfig | None = None`
        # with a silent fallback `stage_config = config or get_stage_config(stage)`.
        #
        # The problem:
        #   1. The fallback is dead code — app.py always passes config explicitly.
        #   2. If someone accidentally omits config in a future call, Python would
        #      silently re-derive it with a second get_stage_config() call.  If
        #      get_stage_config() is ever made non-deterministic (feature flags,
        #      environment lookups, etc.), the two config objects could differ,
        #      leading to subtle size/capacity mismatches between stacks.
        #   3. Having None as a valid value sends the wrong signal — config is
        #      always required for this stack.
        #
        # Fix: make config a required parameter (no default).  Callers that omit
        # it will get a clear TypeError at import time rather than silent drift.
        config: KercelStageConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        database = DatabaseConstruct(
            self,
            "Database",
            stage=stage,
            config=config,
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
        # BUG-02 FIX: self.distribution was previously exposed here because
        # CloudFront was incorrectly placed inside DatabaseConstruct.
        # CloudFront is now in EdgeConstruct (edge.py) / DeliveryStack,
        # where it belongs architecturally.  Removed from DataStack.
