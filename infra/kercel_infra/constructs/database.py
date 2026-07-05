from aws_cdk import CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticache as elasticache
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from kercel_infra.config import KercelStageConfig


class DatabaseConstruct(Construct):
    """DynamoDB tables, S3 buckets, SQS queue, and ElastiCache Redis."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        config: KercelStageConfig,
        vpc: ec2.IVpc,
        redis_security_group: ec2.ISecurityGroup,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_prod = stage == "prod"
        removal_policy = RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY

        self.user_table = dynamodb.Table(
            self,
            "UserTable",
            table_name=f"kercel-users-{stage}",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            point_in_time_recovery=is_prod,
        )

        self.project_table = dynamodb.Table(
            self,
            "ProjectTable",
            table_name=f"kercel-projects-{stage}",
            partition_key=dynamodb.Attribute(
                name="projectId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            point_in_time_recovery=is_prod,
        )
        self.project_table.add_global_secondary_index(
            index_name="byOwnerId",
            partition_key=dynamodb.Attribute(
                name="ownerId", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self.history_table = dynamodb.Table(
            self,
            "HistoryTable",
            table_name=f"kercel-history-{stage}",
            partition_key=dynamodb.Attribute(
                name="projectId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="deploymentId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            point_in_time_recovery=is_prod,
        )
        self.history_table.add_global_secondary_index(
            index_name="byDeploymentId",
            partition_key=dynamodb.Attribute(
                name="deploymentId", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self.deploy_act_table = dynamodb.Table(
            self,
            "DeployActTable",
            table_name=f"kercel-deploy-act-{stage}",
            partition_key=dynamodb.Attribute(
                name="deploymentId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="actionTimestamp", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            point_in_time_recovery=is_prod,
            stream=dynamodb.StreamViewType.NEW_IMAGE,
        )

        self.ws_connections_table = dynamodb.Table(
            self,
            "WsConnectionsTable",
            table_name=f"kercel-ws-connections-{stage}",
            partition_key=dynamodb.Attribute(
                name="connectionId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            time_to_live_attribute="ttl",
        )
        self.ws_connections_table.add_global_secondary_index(
            index_name="byDeploymentId",
            partition_key=dynamodb.Attribute(
                name="deploymentId", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self.artifacts_bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            removal_policy=removal_policy,
            auto_delete_objects=not is_prod,
        )

        self.output_bucket = s3.Bucket(
            self,
            "OutputBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=removal_policy,
            auto_delete_objects=not is_prod,
        )

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
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.output_bucket,
                    origin_access_control=oac,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
            ),
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

        self.deployment_dlq = sqs.Queue(
            self,
            "DeploymentDlq",
            queue_name=f"kercel-deploy-dlq-{stage}",
            retention_period=Duration.days(14),
        )

        self.deployment_queue = sqs.Queue(
            self,
            "DeploymentQueue",
            queue_name=f"kercel-deploy-{stage}",
            visibility_timeout=Duration.minutes(15),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.deployment_dlq,
            ),
        )

        api_subnets = vpc.select_subnets(subnet_group_name="api")

        subnet_group = elasticache.CfnSubnetGroup(
            self,
            "RedisSubnetGroup",
            description=f"Kercel Redis subnet group ({stage})",
            subnet_ids=api_subnets.subnet_ids,
            cache_subnet_group_name=f"kercel-redis-{stage}",
        )

        self.redis_cluster = elasticache.CfnCacheCluster(
            self,
            "RedisCluster",
            cache_node_type=config.redis_node_type,
            engine="redis",
            num_cache_nodes=1,
            cluster_name=f"kercel-redis-{stage}",
            vpc_security_group_ids=[redis_security_group.security_group_id],
            cache_subnet_group_name=subnet_group.cache_subnet_group_name,
        )
        self.redis_cluster.add_dependency(subnet_group)

        CfnOutput(self, "UserTableName", value=self.user_table.table_name)
        CfnOutput(self, "ProjectTableName", value=self.project_table.table_name)
        CfnOutput(self, "HistoryTableName", value=self.history_table.table_name)
        CfnOutput(self, "DeployActTableName", value=self.deploy_act_table.table_name)
        CfnOutput(self, "ArtifactsBucketName", value=self.artifacts_bucket.bucket_name)
        CfnOutput(self, "OutputBucketName", value=self.output_bucket.bucket_name)
        CfnOutput(self, "DeploymentQueueUrl", value=self.deployment_queue.queue_url)
        CfnOutput(
            self,
            "CloudFrontDomainName",
            value=self.distribution.distribution_domain_name,
            description="CloudFront domain for static site delivery",
        )
        CfnOutput(
            self,
            "RedisEndpoint",
            value=self.redis_cluster.attr_redis_endpoint_address,
        )
