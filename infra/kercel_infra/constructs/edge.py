from aws_cdk import CfnOutput
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_globalaccelerator as globalaccelerator
from aws_cdk import aws_globalaccelerator_endpoints as ga_endpoints
from constructs import Construct


class EdgeConstruct(Construct):
    """Global Accelerator for ALB traffic."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        load_balancer: elbv2.IApplicationLoadBalancer,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.accelerator = globalaccelerator.Accelerator(
            self,
            "Accelerator",
            accelerator_name=f"kercel-{stage}",
            enabled=True,
        )

        ga_listener = self.accelerator.add_listener(
            "HttpListener",
            port_ranges=[globalaccelerator.PortRange(from_port=80, to_port=80)],
        )

        ga_listener.add_endpoint_group(
            "AlbEndpointGroup",
            endpoints=[
                ga_endpoints.ApplicationLoadBalancerEndpoint(load_balancer)
            ],
            health_check_port=80,
            health_check_path="/",
            health_check_protocol=globalaccelerator.HealthCheckProtocol.HTTP,
        )

        CfnOutput(
            self,
            "AcceleratorDns",
            value=self.accelerator.dns_name,
            description="Global Accelerator DNS name for deployed apps",
        )
        CfnOutput(
            self,
            "AcceleratorArn",
            value=self.accelerator.accelerator_arn,
        )
