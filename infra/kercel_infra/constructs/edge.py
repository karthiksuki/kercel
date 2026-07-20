from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_globalaccelerator as globalaccelerator
from aws_cdk import aws_globalaccelerator_endpoints as ga_endpoints
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class EdgeConstruct(Construct):
    """Global Accelerator for build-worker ALB traffic AND CloudFront for
    static site delivery from the output S3 bucket.

    BUG-02 FIX: CloudFront was previously inside DatabaseConstruct, which is
    the wrong layer (storage ≠ delivery).  Moving it here:
      1. Keeps separation of concerns clean.
      2. Breaks the circular dependency that would have arisen if compute.py
         needed to know the distribution ID to call CreateInvalidation
         (ComputeStack depends on DataStack, not DeliveryStack — so the ID
         would have been unreachable at synth time).
      3. Lets us write the distribution ID to SSM Parameter Store so EC2
         instances can fetch it at runtime without a cross-stack reference
         that would create a CloudFormation import/export cycle.

    BUG-02 FIX (CloudFront sub-path index.html): CloudFront's
    default_root_object only resolves for the root request ("/").  When a
    browser requests a sub-path like /sites/<projectId>/current/, CloudFront
    passes that path directly to S3.  S3 returns 403 (on a private bucket
    with OAC) or a directory listing — never index.html.

    The fix is a CloudFront Function that runs at the viewer-request stage and
    rewrites directory-style URIs (those ending in "/" or with no file
    extension) to append "/index.html".  This is the same technique used by
    Vercel, Netlify, and Amplify Hosting under the hood.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        load_balancer: elbv2.IApplicationLoadBalancer,
        output_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------------------------
        # CloudFront Function — viewer-request rewrite for sub-path index.html
        #
        # Why a CloudFront Function and not Lambda@Edge?
        #   • CloudFront Functions run at every PoP with ~1ms latency and
        #     sub-millisecond execution time — essentially zero overhead.
        #   • Lambda@Edge adds 5–50ms of cold-start latency and costs 3×more.
        #   • This is a pure URI rewrite with no async work, making it a
        #     perfect CloudFront Function use-case.
        #
        # Logic:
        #   /sites/proj/current/       → /sites/proj/current/index.html
        #   /sites/proj/current/about  → /sites/proj/current/about/index.html
        #   /sites/proj/current/main.js (has extension) → unchanged
        # -------------------------------------------------------------------
        index_rewrite_fn = cloudfront.Function(
            self,
            "IndexHtmlRewrite",
            function_name=f"kercel-index-rewrite-{stage}",
            code=cloudfront.FunctionCode.from_inline(
                """
function handler(event) {
    var request = event.request;
    var uri = request.uri;

    // Append index.html for trailing-slash requests (directory index)
    if (uri.endsWith('/')) {
        request.uri = uri + 'index.html';
        return request;
    }

    // For paths with no file extension (e.g. /about, /dashboard),
    // treat as an SPA route and serve index.html from the same prefix.
    // This supports React Router / Next.js static export client-side routing.
    var lastSegment = uri.split('/').pop();
    if (lastSegment && !lastSegment.match(/\\.[^/]+$/)) {
        request.uri = uri + '/index.html';
    }

    return request;
}
"""
            ),
            runtime=cloudfront.FunctionRuntime.JS_2_0,
        )

        # -------------------------------------------------------------------
        # Origin Access Control (OAC) — the modern replacement for OAI.
        # OAC uses SigV4 to sign every request from CloudFront to S3, so the
        # bucket can remain fully private (BLOCK_ALL public access) while
        # CloudFront still reads from it.  The CDK's
        # S3BucketOrigin.with_origin_access_control() automatically adds the
        # required bucket policy statement.
        # -------------------------------------------------------------------
        oac = cloudfront.S3OriginAccessControl(
            self,
            "OutputBucketOac",
            origin_access_control_name=f"kercel-output-oac-{stage}",
            signing=cloudfront.Signing.SIGV4_ALWAYS,
        )

        self.distribution = cloudfront.Distribution(
            self,
            "SitesDistribution",
            comment=f"Kercel deployed sites ({stage})",
            # default_root_object is intentionally omitted here because we rely
            # on the CloudFront Function above to rewrite every directory request
            # to index.html at the sub-path level.  Setting default_root_object
            # only helps the bare "/" request and would conflict with sub-paths.
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    output_bucket,
                    origin_access_control=oac,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
                # Attach the index.html rewrite function at viewer-request stage
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=index_rewrite_fn,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            # Error handling: if S3 returns 403 (key not found with OAC) or
            # 404, redirect to the project's index.html for SPA deep linking.
            # TTL=None means CloudFront uses its default (300s); setting it to
            # 0 would mean every 404 hits S3 again which is expensive.
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=None,
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=None,
                ),
            ],
        )

        # -------------------------------------------------------------------
        # Write the CloudFront distribution ID to SSM Parameter Store.
        #
        # Why SSM and not a cross-stack export?
        #   Cross-stack CloudFormation exports create a hard dependency: the
        #   exporting stack cannot be updated if the importing stack exists.
        #   Because ComputeStack deploys BEFORE DeliveryStack (the dependency
        #   graph requires it), the distribution ID doesn't exist yet at
        #   ComputeStack deploy time — so a cross-stack reference would create
        #   an unsolvable chicken-and-egg cycle.
        #
        #   SSM Parameter Store solves this: the EC2 worker script reads the
        #   parameter at runtime (after DeliveryStack has been deployed), not
        #   at CloudFormation synth time.  The worker gracefully skips
        #   invalidation if the parameter doesn't exist yet (first deploy race).
        # -------------------------------------------------------------------
        ssm.StringParameter(
            self,
            "CloudFrontDistributionIdParam",
            parameter_name=f"/kercel/{stage}/cloudfront-distribution-id",
            string_value=self.distribution.distribution_id,
            description=f"CloudFront distribution ID for Kercel {stage} site delivery",
        )

        # -------------------------------------------------------------------
        # Global Accelerator for ALB (build-worker control plane).
        # BUG-07 NOTE: HTTPS is not yet configured (no ACM certificate is
        # provisioned in this stack).  The Global Accelerator and ALB currently
        # only serve HTTP on port 80.  To enable HTTPS:
        #   1. Create an ACM certificate in us-east-1 for your domain.
        #   2. Add an HTTPS listener to the ALB in compute.py.
        #   3. Add port range 443 to the Global Accelerator listener below.
        # This is tracked as a TODO — the security group already allows 443
        # but the certificate infrastructure is out of scope for this patch.
        # -------------------------------------------------------------------
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

        # Outputs
        CfnOutput(
            self,
            "AcceleratorDns",
            value=self.accelerator.dns_name,
            description="Global Accelerator DNS name for build-worker API",
        )
        CfnOutput(
            self,
            "AcceleratorArn",
            value=self.accelerator.accelerator_arn,
        )
        CfnOutput(
            self,
            "CloudFrontDomainName",
            value=self.distribution.distribution_domain_name,
            description=(
                "CloudFront domain for deployed sites. "
                f"Access a project at: https://<domain>/sites/<projectId>/current/"
            ),
        )
        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID (also in SSM at /kercel/{stage}/cloudfront-distribution-id)",
        )
