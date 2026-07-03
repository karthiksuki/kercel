from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_prod = stage == "prod"
        removal_policy = RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY

        self.projects_table = dynamodb.Table(
            self,
            "ProjectsTable",
            table_name=f"kercel-projects-{stage}",
            partition_key=dynamodb.Attribute(
                name="projectId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            point_in_time_recovery=is_prod,
        )
        self.projects_table.add_global_secondary_index(
            index_name="byGithubUrl",
            partition_key=dynamodb.Attribute(
                name="githubUrl", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self.deployments_table = dynamodb.Table(
            self,
            "DeploymentsTable",
            table_name=f"kercel-deployments-{stage}",
            partition_key=dynamodb.Attribute(
                name="deploymentId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="createdAt", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
            point_in_time_recovery=is_prod,
        )
        self.deployments_table.add_global_secondary_index(
            index_name="byProjectId",
            partition_key=dynamodb.Attribute(
                name="projectId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="createdAt", type=dynamodb.AttributeType.STRING
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

        CfnOutput(self, "ProjectsTableName", value=self.projects_table.table_name)
        CfnOutput(self, "DeploymentsTableName", value=self.deployments_table.table_name)
        CfnOutput(self, "ArtifactsBucketName", value=self.artifacts_bucket.bucket_name)
        CfnOutput(self, "DeploymentQueueUrl", value=self.deployment_queue.queue_url)
