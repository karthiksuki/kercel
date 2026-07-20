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
    description="Kercel VPC, subnets, and security groups",
)

data = DataStack(
    app,
    f"{stack_prefix}-Data",
    stage=stage,
    # BUG-18 FIX: config is now a required positional-keyword argument in DataStack
    # (the None-fallback was removed).  Always pass it explicitly.
    config=config,
    vpc=network.vpc,
    redis_security_group=network.redis_security_group,
    env=env,
    description="Kercel DynamoDB, S3, SQS, and Redis",
)
data.add_dependency(network)

compute = ComputeStack(
    app,
    f"{stack_prefix}-Compute",
    stage=stage,
    config=config,
    vpc=network.vpc,
    alb_security_group=network.alb_security_group,
    compute_security_group=network.compute_security_group,
    history_table=data.history_table,
    deploy_act_table=data.deploy_act_table,
    artifacts_bucket=data.artifacts_bucket,
    output_bucket=data.output_bucket,
    deployment_queue=data.deployment_queue,
    env=env,
    description="Kercel EC2 build workers and ALB",
)
compute.add_dependency(network)
compute.add_dependency(data)

api = ApiStack(
    app,
    f"{stack_prefix}-Api",
    stage=stage,
    vpc=network.vpc,
    api_lambda_security_group=network.api_lambda_security_group,
    user_table=data.user_table,
    project_table=data.project_table,
    history_table=data.history_table,
    deploy_act_table=data.deploy_act_table,
    ws_connections_table=data.ws_connections_table,
    deployment_queue=data.deployment_queue,
    redis_cluster=data.redis_cluster,
    env=env,
    description="Kercel REST and WebSocket APIs",
)
api.add_dependency(network)
api.add_dependency(data)

delivery = DeliveryStack(
    app,
    f"{stack_prefix}-Delivery",
    stage=stage,
    load_balancer=compute.load_balancer,
    # BUG-02 FIX: pass output_bucket so DeliveryStack/EdgeConstruct can create
    # the CloudFront distribution pointing at it.  Previously CloudFront was
    # created inside DataStack (DatabaseConstruct) with no way to invalidate
    # after builds because the distribution ID was unavailable to ComputeStack.
    output_bucket=data.output_bucket,
    env=env,
    description="Kercel Global Accelerator + CloudFront site delivery",
)
delivery.add_dependency(compute)
# DeliveryStack also depends on DataStack because it reads output_bucket.
delivery.add_dependency(data)

cdk.Tags.of(app).add("project", "kercel")
cdk.Tags.of(app).add("stage", stage)

app.synth()
