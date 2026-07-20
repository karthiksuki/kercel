from aws_cdk import CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticache as elasticache
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from kercel_infra.config import KercelStageConfig


class DatabaseConstruct(Construct):
    """DynamoDB tables, S3 buckets, SQS queue, and ElastiCache Redis.

    BUG-02 FIX (structural): CloudFront was previously created inside this
    construct, which is semantically wrong — a database construct should only
    own storage resources.  CloudFront is a delivery/edge concern and now lives
    in EdgeConstruct (edge.py) which is composed by DeliveryStack.

    Having CloudFront here also made it impossible to pass the distribution ID
    to the ComputeStack (which depends on DataStack, not DeliveryStack), causing
    a CDK circular dependency.  Separating it removes the cycle.
    """

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

        # -------------------------------------------------------------------
        # BUG-03 FIX: SQS visibility timeout increased from 15 → 60 minutes.
        #
        # The original setting was Duration.minutes(15).  The worker.sh polling
        # loop requests --visibility-timeout 900 (15 min) per message.  If a
        # real build takes longer than 15 minutes (common on t3.micro with a
        # large Next.js app), the message becomes visible again before the
        # worker finishes, and a SECOND worker instance picks it up — causing
        # two concurrent builds for the same deployment, double S3 writes, and
        # a race condition on update_status.
        #
        # Fix: set the queue-level timeout to 60 minutes.  The queue-level
        # value is the effective cap; the receive-message call value is ignored
        # if it exceeds the queue setting.  60 minutes covers real-world builds
        # comfortably while still allowing timely DLQ promotion if the worker
        # crashes without deleting the message.
        # -------------------------------------------------------------------
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
            visibility_timeout=Duration.minutes(60),  # was 15 — see BUG-03 above
            dead_letter_queue=sqs.DeadLetterQueue(
                # BUG-13 FIX (partial): Increased from 3 → 5 retries.
                # With max_receive_count=3, a build that fails twice due to
                # transient errors (GitHub rate limit, npm registry blip, S3
                # throttle) would permanently dead-letter on the 3rd attempt
                # with no recovery chance.  5 retries gives enough headroom
                # for short-lived transient failures while still preventing
                # infinite retry loops for genuinely broken projects.
                max_receive_count=5,
                queue=self.deployment_dlq,
            ),
        )

        # -------------------------------------------------------------------
        # BUG-13 FIX (continued): CloudWatch alarm on DLQ depth.
        #
        # Without an alarm, failed deployments silently accumulate in the DLQ
        # with no operator notification.  This alarm fires as soon as 1 message
        # lands in the DLQ so the team is alerted immediately.
        # -------------------------------------------------------------------
        cloudwatch.Alarm(
            self,
            "DlqDepthAlarm",
            alarm_name=f"kercel-dlq-depth-{stage}",
            alarm_description=(
                "One or more deployment jobs have failed all retry attempts "
                "and landed in the dead-letter queue. Check build logs."
            ),
            metric=self.deployment_dlq.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(1),
                statistic="Maximum",
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
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

        # CloudFormation outputs — only expose what operators genuinely need.
        # BUG-17 FIX: RedisEndpoint is an internal VPC hostname; exposing it
        # in CloudFormation outputs leaks network topology to anyone with
        # cloudformation:DescribeStacks access.  Removed.
        CfnOutput(self, "UserTableName", value=self.user_table.table_name)
        CfnOutput(self, "ProjectTableName", value=self.project_table.table_name)
        CfnOutput(self, "HistoryTableName", value=self.history_table.table_name)
        CfnOutput(self, "DeployActTableName", value=self.deploy_act_table.table_name)
        CfnOutput(self, "ArtifactsBucketName", value=self.artifacts_bucket.bucket_name)
        CfnOutput(self, "OutputBucketName", value=self.output_bucket.bucket_name)
        CfnOutput(self, "DeploymentQueueUrl", value=self.deployment_queue.queue_url)
