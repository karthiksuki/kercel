from aws_cdk import Stack
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_s3 as s3
from constructs import Construct

from kercel_infra.constructs.edge import EdgeConstruct


class DeliveryStack(Stack):
    """Delivery layer: Global Accelerator (for ALB) + CloudFront (for static sites).

    BUG-02 FIX: Previously this stack only wrapped the ALB in Global Accelerator.
    CloudFront was incorrectly living inside DatabaseConstruct.

    DeliveryStack now owns both delivery mechanisms:
      • Global Accelerator → routes traffic to the build-worker ALB (control plane)
      • CloudFront → serves built static sites from the output S3 bucket

    The output_bucket is passed from DataStack so EdgeConstruct can configure the
    CloudFront origin and write the distribution ID to SSM.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        load_balancer: elbv2.IApplicationLoadBalancer,
        output_bucket: s3.IBucket,  # BUG-02 FIX: new parameter — the S3 bucket CloudFront reads from
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        edge = EdgeConstruct(
            self,
            "Edge",
            stage=stage,
            load_balancer=load_balancer,
            output_bucket=output_bucket,
        )

        self.accelerator = edge.accelerator
        self.distribution = edge.distribution
