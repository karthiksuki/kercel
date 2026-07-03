from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"kercel-{stage}",
            max_azs=2,
            nat_gateways=2 if stage == "prod" else 1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private",
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

        self.instance_security_group = ec2.SecurityGroup(
            self,
            "InstanceSecurityGroup",
            vpc=self.vpc,
            description="Ingress for Kercel EC2 hosts",
            allow_all_outbound=True,
        )
        self.instance_security_group.add_ingress_rule(
            self.alb_security_group, ec2.Port.tcp(80), "HTTP from ALB"
        )
        self.instance_security_group.add_ingress_rule(
            self.alb_security_group, ec2.Port.tcp(443), "HTTPS from ALB"
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
