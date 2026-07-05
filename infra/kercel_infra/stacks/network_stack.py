from aws_cdk import Stack
from constructs import Construct

from kercel_infra.constructs.networking import NetworkingConstruct


class NetworkStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        networking = NetworkingConstruct(
            self,
            "Networking",
            stage=stage,
        )

        self.vpc = networking.vpc
        self.alb_security_group = networking.alb_security_group
        self.compute_security_group = networking.compute_security_group
        self.api_lambda_security_group = networking.api_lambda_security_group
        self.redis_security_group = networking.redis_security_group
