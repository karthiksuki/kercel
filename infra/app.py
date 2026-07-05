#!/usr/bin/env python3
import os

import aws_cdk as cdk

from kercel_infra.config import get_stage_config
from kercel_infra.stacks.api_stack import ApiStack
from kercel_infra.stacks.compute_stack import ComputeStack
from kercel_infra.stacks.data_stack import DataStack
from kercel_infra.stacks.delivery_stack import DeliveryStack
from kercel_infra.stacks.network_stack import NetworkStack

app = cdk.App()

stage = app.node.try_get_context("stage") or os.environ.get("KERCEL_STAGE", "dev")
config = get_stage_config(stage)

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

stack_prefix = f"Kercel-{stage}"

network = NetworkStack(
    app,
    f"{stack_prefix}-Network",
    stage=stage,
    env=env,
    description="Kercel VPC and security groups",
)

data = DataStack(
    app,
    f"{stack_prefix}-Data",
    stage=stage,
    env=env,
    description="Kercel DynamoDB tables, S3 artifacts, and deployment queue",
)

compute = ComputeStack(
    app,
    f"{stack_prefix}-Compute",
    stage=stage,
    config=config,
    vpc=network.vpc,
    alb_security_group=network.alb_security_group,
    instance_security_group=network.instance_security_group,
    projects_table=data.projects_table,
    deployments_table=data.deployments_table,
    artifacts_bucket=data.artifacts_bucket,
    deployment_queue=data.deployment_queue,
    env=env,
    description="Kercel EC2 hosts, ALB, and deployment worker Lambda",
)
compute.add_dependency(network)
compute.add_dependency(data)

api = ApiStack(
    app,
    f"{stack_prefix}-Api",
    stage=stage,
    projects_table=data.projects_table,
    deployments_table=data.deployments_table,
    deployment_queue=data.deployment_queue,
    env=env,
    description="Kercel REST API (GitHub project intake and deployments)",
)
api.add_dependency(data)

delivery = DeliveryStack(
    app,
    f"{stack_prefix}-Delivery",
    stage=stage,
    load_balancer=compute.load_balancer,
    env=env,
    description="Kercel Global Accelerator for global app delivery",
)
delivery.add_dependency(compute)

cdk.Tags.of(app).add("project", "kercel")
cdk.Tags.of(app).add("stage", stage)

app.synth()
