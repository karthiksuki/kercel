import os

from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from kercel_infra.config import KercelStageConfig


class ComputeConstruct(Construct):
    """EC2 build workers (SQS polling) and Application Load Balancer."""

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

        instance_role = iam.Role(
            self,
            "BuildWorkerRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Kercel build worker role for SQS polling and artifact upload",
        )
        instance_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        deployment_queue.grant_consume_messages(instance_role)
        artifacts_bucket.grant_read_write(instance_role)
        output_bucket.grant_read_write(instance_role)
        history_table.grant_read_write_data(instance_role)
        deploy_act_table.grant_read_write_data(instance_role)

        instance_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ec2:DescribeInstances"],
                resources=["*"],
            )
        )
        instance_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        worker_script_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "lambda", "build-worker", "worker.sh"
        )
        with open(worker_script_path, encoding="utf-8") as f:
            worker_script = f.read()

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "set -euxo pipefail",
            "dnf update -y",
            "dnf install -y git nodejs npm aws-cli",
            f"export DEPLOYMENT_QUEUE_URL={deployment_queue.queue_url}",
            f"export HISTORY_TABLE={history_table.table_name}",
            f"export DEPLOY_ACT_TABLE={deploy_act_table.table_name}",
            f"export ARTIFACTS_BUCKET={artifacts_bucket.bucket_name}",
            f"export OUTPUT_BUCKET={output_bucket.bucket_name}",
            f"export STAGE={stage}",
            "mkdir -p /opt/kercel",
            f"cat > /opt/kercel/worker.sh <<'WORKER_EOF'\n{worker_script}\nWORKER_EOF",
            "chmod +x /opt/kercel/worker.sh",
            "cat > /etc/systemd/system/kercel-worker.service <<'EOF'",
            "[Unit]",
            "Description=Kercel build worker (SQS poller)",
            "After=network.target",
            "",
            "[Service]",
            "Type=simple",
            "Environment=DEPLOYMENT_QUEUE_URL="
            + deployment_queue.queue_url,
            "Environment=HISTORY_TABLE=" + history_table.table_name,
            "Environment=DEPLOY_ACT_TABLE=" + deploy_act_table.table_name,
            "Environment=ARTIFACTS_BUCKET=" + artifacts_bucket.bucket_name,
            "Environment=OUTPUT_BUCKET=" + output_bucket.bucket_name,
            "Environment=STAGE=" + stage,
            "ExecStart=/opt/kercel/worker.sh",
            "Restart=always",
            "RestartSec=10",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "EOF",
            "systemctl daemon-reload",
            "systemctl enable kercel-worker",
            "systemctl start kercel-worker",
            "dnf install -y nginx",
            "mkdir -p /var/www/kercel/current",
            "cat > /etc/nginx/conf.d/kercel.conf <<'NGINX_EOF'",
            "server {",
            "    listen 80 default_server;",
            "    server_name _;",
            "    root /var/www/kercel/current;",
            "    index index.html;",
            "    location / {",
            "        try_files $uri $uri/ /index.html;",
            "    }",
            "}",
            "NGINX_EOF",
            "systemctl enable nginx",
            "systemctl restart nginx",
        )

        self.auto_scaling_group = autoscaling.AutoScalingGroup(
            self,
            "BuildWorkerAsg",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="compute"),
            security_group=compute_security_group,
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
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="public"),
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

        CfnOutput(
            self,
            "LoadBalancerDns",
            value=self.load_balancer.load_balancer_dns_name,
        )
