import os

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from kercel_infra.config import KercelStageConfig


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
        instance_security_group: ec2.ISecurityGroup,
        projects_table: dynamodb.ITable,
        deployments_table: dynamodb.ITable,
        artifacts_bucket: s3.IBucket,
        deployment_queue: sqs.IQueue,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        instance_role = iam.Role(
            self,
            "HostInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Kercel EC2 host role for artifact fetch and SSM management",
        )
        artifacts_bucket.grant_read(instance_role)
        instance_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "set -euxo pipefail",
            "dnf update -y",
            "dnf install -y nginx git nodejs npm",
            "systemctl enable nginx",
            "mkdir -p /var/www/kercel",
            "chown -R nginx:nginx /var/www/kercel",
            "cat > /etc/nginx/conf.d/kercel.conf <<'EOF'",
            "server {",
            "    listen 80 default_server;",
            "    server_name _;",
            "    root /var/www/kercel/current;",
            "    index index.html;",
            "    location / {",
            "        try_files $uri $uri/ /index.html;",
            "    }",
            "}",
            "EOF",
            "systemctl restart nginx",
        )

        self.auto_scaling_group = autoscaling.AutoScalingGroup(
            self,
            "HostAsg",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_group=instance_security_group,
            instance_type=ec2.InstanceType(config.instance_type),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            role=instance_role,
            user_data=user_data,
            min_capacity=config.min_capacity,
            max_capacity=config.max_capacity,
            desired_capacity=config.desired_capacity,
            health_check=autoscaling.HealthCheck.elb(grace=Duration.minutes(5)),
        )

        self.load_balancer = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        listener = self.load_balancer.add_listener(
            "HttpListener",
            port=80,
            open=False,
        )
        listener.add_targets(
            "AsgTargets",
            port=80,
            targets=[self.auto_scaling_group],
            health_check=elbv2.HealthCheck(
                path="/",
                healthy_http_codes="200-399",
            ),
        )

        lambda_dir = os.path.join(os.path.dirname(__file__), "..", "..", "lambda")

        deploy_worker = lambda_.Function(
            self,
            "DeployWorker",
            function_name=f"kercel-deploy-worker-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(lambda_dir, "deploy_worker")),
            timeout=Duration.minutes(5),
            memory_size=1024,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "STAGE": stage,
                "PROJECTS_TABLE": projects_table.table_name,
                "DEPLOYMENTS_TABLE": deployments_table.table_name,
                "ARTIFACTS_BUCKET": artifacts_bucket.bucket_name,
                "DEPLOYMENT_QUEUE_URL": deployment_queue.queue_url,
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        projects_table.grant_read_write_data(deploy_worker)
        deployments_table.grant_read_write_data(deploy_worker)
        artifacts_bucket.grant_read_write(deploy_worker)
        deployment_queue.grant_consume_messages(deploy_worker)

        deploy_worker.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ssm:SendCommand",
                    "ssm:GetCommandInvocation",
                    "ssm:ListCommands",
                ],
                resources=["*"],
            )
        )
        deploy_worker.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ec2:DescribeInstances"],
                resources=["*"],
            )
        )

        deploy_worker.add_event_source(
            lambda_event_sources.SqsEventSource(
                deployment_queue,
                batch_size=1,
                report_batch_item_failures=True,
            )
        )

        CfnOutput(self, "LoadBalancerDns", value=self.load_balancer.load_balancer_dns_name)
        CfnOutput(self, "DeployWorkerArn", value=deploy_worker.function_arn)
