from aws_cdk import Stack
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from constructs import Construct

from kercel_infra.constructs.edge import EdgeConstruct


class DeliveryStack(Stack):
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

        edge = EdgeConstruct(
            self,
            "Edge",
            stage=stage,
            load_balancer=load_balancer,
        )

        self.accelerator = edge.accelerator
