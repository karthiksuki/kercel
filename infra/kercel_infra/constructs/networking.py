from aws_cdk import CfnOutput
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkingConstruct(Construct):
    """VPC with public, compute, and API tiers plus security groups and VPC endpoints."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_prod = stage == "prod"

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"kercel-{stage}",
            max_azs=2,
            nat_gateways=2 if is_prod else 1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="compute",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="api",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        self.alb_security_group = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=self.vpc,
            description="Ingress for Kercel application load balancer",
            allow_all_outbound=True,
        )
        self.alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP"
        )
        self.alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS"
        )

        self.compute_security_group = ec2.SecurityGroup(
            self,
            "ComputeSecurityGroup",
            vpc=self.vpc,
            description="Build worker EC2 instances",
            allow_all_outbound=True,
        )
        self.compute_security_group.add_ingress_rule(
            self.alb_security_group, ec2.Port.tcp(80), "HTTP from ALB"
        )
        self.compute_security_group.add_ingress_rule(
            self.alb_security_group, ec2.Port.tcp(443), "HTTPS from ALB"
        )

        self.api_lambda_security_group = ec2.SecurityGroup(
            self,
            "ApiLambdaSecurityGroup",
            vpc=self.vpc,
            description="VPC-attached API Lambda functions",
            allow_all_outbound=True,
        )

        self.redis_security_group = ec2.SecurityGroup(
            self,
            "RedisSecurityGroup",
            vpc=self.vpc,
            description="ElastiCache Redis cluster",
            allow_all_outbound=True,
        )
        self.redis_security_group.add_ingress_rule(
            self.api_lambda_security_group,
            ec2.Port.tcp(6379),
            "Redis from API Lambdas",
        )
        self.redis_security_group.add_ingress_rule(
            self.compute_security_group,
            ec2.Port.tcp(6379),
            "Redis from build workers",
        )

        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )

        api_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            one_per_az=True,
        )

        self.vpc.add_interface_endpoint(
            "SqsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SQS,
            subnets=api_subnets,
            private_dns_enabled=True,
        )
        self.vpc.add_interface_endpoint(
            "S3Endpoint",
            service=ec2.InterfaceVpcEndpointAwsService.S3,
            subnets=api_subnets,
            private_dns_enabled=True,
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
