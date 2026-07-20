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
        # Port 443 is allowed on the ALB SG in anticipation of the future ACM
        # certificate + HTTPS listener (tracked as BUG-07 TODO in edge.py).
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
        # BUG-09 FIX: The compute SG previously allowed port 443 from the ALB,
        # but nginx on the EC2 instances only listens on port 80 (there is no
        # TLS termination at the instance — TLS terminates at the ALB).
        # Allowing 443 into instances that don't listen on it is dead, misleading
        # noise that suggests TLS-at-instance was intended (it wasn't).
        # Removed the 443 rule; only port 80 (HTTP from ALB → nginx) is needed.
        self.compute_security_group.add_ingress_rule(
            self.alb_security_group, ec2.Port.tcp(80), "HTTP from ALB"
        )
        # (443 rule removed — nginx only listens on 80; TLS terminates at ALB)

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

        # DynamoDB — Gateway endpoint (correct: free, no DNS override, routes
        # DynamoDB traffic within the AWS backbone instead of over the NAT).
        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )

        # BUG-08 FIX: S3 was configured as an Interface endpoint (PrivateLink).
        # This is wrong for two reasons:
        #
        # 1. Cost: Interface endpoints charge ~$7/month per AZ plus per-GB data
        #    transfer fees.  Gateway endpoints for S3 and DynamoDB are free.
        #
        # 2. DNS override: enabling private_dns_enabled=True on the S3 interface
        #    endpoint rewrites the public S3 DNS (*.s3.amazonaws.com) for all
        #    subnets in the VPC.  This can break EC2 instances that need to reach
        #    S3 endpoints in other regions (e.g. for npm packages, apt, dnf),
        #    because the interface endpoint only covers the current region.
        #
        # Fix: use a Gateway endpoint for S3, exactly as we do for DynamoDB.
        # Gateway endpoints are the AWS-recommended, cost-free option and they
        # do not interfere with DNS resolution.
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # SQS — Interface endpoint is correct here (SQS has no gateway option).
        # Keep private_dns_enabled=True so Lambda/EC2 code can use the standard
        # SQS SDK endpoint URL without any configuration changes.
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

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
