from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from kercel_infra.config import KercelStageConfig
from kercel_infra.constructs.compute import ComputeConstruct


class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        config: KercelStageConfig,
        vpc: ec2.IVpc,
        alb_security_group: ec2.ISecurityGroup,
        compute_security_group: ec2.ISecurityGroup,
        history_table: dynamodb.ITable,
        deploy_act_table: dynamodb.ITable,
        artifacts_bucket: s3.IBucket,
        output_bucket: s3.IBucket,
        deployment_queue: sqs.IQueue,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        compute = ComputeConstruct(
            self,
            "Compute",
            stage=stage,
            config=config,
            vpc=vpc,
            alb_security_group=alb_security_group,
            compute_security_group=compute_security_group,
            history_table=history_table,
            deploy_act_table=deploy_act_table,
            artifacts_bucket=artifacts_bucket,
            output_bucket=output_bucket,
            deployment_queue=deployment_queue,
        )

        self.auto_scaling_group = compute.auto_scaling_group
        self.load_balancer = compute.load_balancer
