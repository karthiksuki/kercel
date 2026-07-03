import os

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        projects_table: dynamodb.ITable,
        deployments_table: dynamodb.ITable,
        deployment_queue: sqs.IQueue,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_dir = os.path.join(os.path.dirname(__file__), "..", "..", "lambda")

        api_handler = lambda_.Function(
            self,
            "ApiHandler",
            function_name=f"kercel-api-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(lambda_dir, "api")),
            timeout=Duration.seconds(29),
            memory_size=512,
            environment={
                "STAGE": stage,
                "PROJECTS_TABLE": projects_table.table_name,
                "DEPLOYMENTS_TABLE": deployments_table.table_name,
                "DEPLOYMENT_QUEUE_URL": deployment_queue.queue_url,
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        projects_table.grant_read_write_data(api_handler)
        deployments_table.grant_read_write_data(api_handler)
        deployment_queue.grant_send_messages(api_handler)

        self.api = apigateway.RestApi(
            self,
            "KercelApi",
            rest_api_name=f"kercel-api-{stage}",
            description="Kercel control plane API",
            deploy_options=apigateway.StageOptions(
                stage_name=stage,
                throttling_rate_limit=100,
                throttling_burst_limit=200,
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        integration = apigateway.LambdaIntegration(api_handler)

        projects = self.api.root.add_resource("projects")
        projects.add_method("POST", integration)
        projects.add_method("GET", integration)

        project = projects.add_resource("{projectId}")
        project.add_method("GET", integration)

        deployments = project.add_resource("deployments")
        deployments.add_method("POST", integration)
        deployments.add_method("GET", integration)

        deployment = deployments.add_resource("{deploymentId}")
        deployment.add_method("GET", integration)

        CfnOutput(
            self,
            "ApiUrl",
            value=self.api.url,
            description="Kercel API base URL",
        )
