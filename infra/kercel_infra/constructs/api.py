import os

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class ApiConstruct(Construct):
    """REST and WebSocket API Gateways with per-route Python Lambdas."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        vpc: ec2.IVpc,
        api_lambda_security_group: ec2.ISecurityGroup,
        user_table: dynamodb.ITable,
        project_table: dynamodb.ITable,
        history_table: dynamodb.ITable,
        deploy_act_table: dynamodb.ITable,
        ws_connections_table: dynamodb.ITable,
        deployment_queue: sqs.IQueue,
        redis_endpoint: str,
        redis_port: str = "6379",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_root = os.path.join(
            os.path.dirname(__file__), "..", "..", "lambda"
        )
        api_subnets = ec2.SubnetSelection(subnet_group_name="api")

        shared_layer = lambda_.LayerVersion(
            self,
            "SharedLayer",
            code=lambda_.Code.from_asset(os.path.join(lambda_root, "layer")),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Kercel shared Lambda utilities",
        )

        redis_env = {
            "REDIS_HOST": redis_endpoint,
            "REDIS_PORT": redis_port,
            "STAGE": stage,
        }

        create_project_fn = self._python_function(
            "CreateProjectFn",
            function_name=f"kercel-create-project-{stage}",
            handler_dir=os.path.join(lambda_root, "create_project"),
            layers=[shared_layer],
            vpc=vpc,
            api_subnets=api_subnets,
            api_lambda_security_group=api_lambda_security_group,
            environment={
                **redis_env,
                "PROJECT_TABLE": project_table.table_name,
            },
        )
        project_table.grant_read_write_data(create_project_fn)

        get_user_fn = self._python_function(
            "GetUserFn",
            function_name=f"kercel-get-user-{stage}",
            handler_dir=os.path.join(lambda_root, "get_user"),
            layers=[shared_layer],
            vpc=vpc,
            api_subnets=api_subnets,
            api_lambda_security_group=api_lambda_security_group,
            environment={
                **redis_env,
                "USER_TABLE": user_table.table_name,
            },
        )
        user_table.grant_read_data(get_user_fn)

        create_deployment_fn = self._python_function(
            "CreateDeploymentFn",
            function_name=f"kercel-create-deployment-{stage}",
            handler_dir=os.path.join(lambda_root, "create_deployment"),
            layers=[shared_layer],
            vpc=vpc,
            api_subnets=api_subnets,
            api_lambda_security_group=api_lambda_security_group,
            environment={
                **redis_env,
                "PROJECT_TABLE": project_table.table_name,
                "HISTORY_TABLE": history_table.table_name,
                "DEPLOY_ACT_TABLE": deploy_act_table.table_name,
                "DEPLOYMENT_QUEUE_URL": deployment_queue.queue_url,
            },
        )
        project_table.grant_read_data(create_deployment_fn)
        history_table.grant_read_write_data(create_deployment_fn)
        deploy_act_table.grant_read_write_data(create_deployment_fn)
        deployment_queue.grant_send_messages(create_deployment_fn)

        get_deployment_fn = self._python_function(
            "GetDeploymentFn",
            function_name=f"kercel-get-deployment-{stage}",
            handler_dir=os.path.join(lambda_root, "get_deployment"),
            layers=[shared_layer],
            vpc=vpc,
            api_subnets=api_subnets,
            api_lambda_security_group=api_lambda_security_group,
            environment={
                **redis_env,
                "HISTORY_TABLE": history_table.table_name,
                "DEPLOY_ACT_TABLE": deploy_act_table.table_name,
            },
        )
        history_table.grant_read_data(get_deployment_fn)
        deploy_act_table.grant_read_data(get_deployment_fn)
        get_deployment_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[
                    history_table.table_arn,
                    f"{history_table.table_arn}/index/*",
                    deploy_act_table.table_arn,
                ],
            )
        )

        log_streamer_fn = self._python_function(
            "LogStreamerFn",
            function_name=f"kercel-log-streamer-{stage}",
            handler_dir=os.path.join(lambda_root, "log_streamer"),
            layers=[shared_layer],
            vpc=vpc,
            api_subnets=api_subnets,
            api_lambda_security_group=api_lambda_security_group,
            timeout=Duration.seconds(30),
            environment={
                **redis_env,
                "DEPLOY_ACT_TABLE": deploy_act_table.table_name,
                "WS_CONNECTIONS_TABLE": ws_connections_table.table_name,
            },
        )
        deploy_act_table.grant_read_data(log_streamer_fn)
        ws_connections_table.grant_read_write_data(log_streamer_fn)
        log_streamer_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=["*"],
            )
        )

        log_streamer_fn.add_event_source(
            lambda_event_sources.DynamoEventSource(
                deploy_act_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                retry_attempts=2,
            )
        )

        self.rest_api = apigateway.RestApi(
            self,
            "KercelRestApi",
            rest_api_name=f"kercel-api-{stage}",
            description="Kercel control plane REST API",
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

        projects = self.rest_api.root.add_resource("projects")
        projects.add_method(
            "POST",
            apigateway.LambdaIntegration(create_project_fn),
        )

        users = self.rest_api.root.add_resource("users")
        user = users.add_resource("{id}")
        user.add_method(
            "GET",
            apigateway.LambdaIntegration(get_user_fn),
        )

        deployments = self.rest_api.root.add_resource("deployments")
        deployments.add_method(
            "POST",
            apigateway.LambdaIntegration(create_deployment_fn),
        )
        deployment = deployments.add_resource("{id}")
        deployment.add_method(
            "GET",
            apigateway.LambdaIntegration(get_deployment_fn),
        )

        self.websocket_api = apigwv2.WebSocketApi(
            self,
            "KercelWebSocketApi",
            api_name=f"kercel-ws-{stage}",
            description="Kercel real-time deployment log stream",
            connect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "ConnectIntegration",
                    log_streamer_fn,
                ),
            ),
            disconnect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "DisconnectIntegration",
                    log_streamer_fn,
                ),
            ),
            default_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "DefaultIntegration",
                    log_streamer_fn,
                ),
            ),
        )

        self.websocket_stage = apigwv2.WebSocketStage(
            self,
            "WebSocketStage",
            web_socket_api=self.websocket_api,
            stage_name=stage,
            auto_deploy=True,
        )

        log_streamer_fn.add_environment(
            "WEBSOCKET_API_ENDPOINT",
            f"https://{self.websocket_api.api_id}.execute-api."
            f"{Stack.of(self).region}.amazonaws.com/{stage}",
        )

        CfnOutput(
            self,
            "RestApiUrl",
            value=self.rest_api.url,
            description="Kercel REST API base URL",
        )
        CfnOutput(
            self,
            "WebSocketApiUrl",
            value=self.websocket_stage.url,
            description="Kercel WebSocket API URL (append ?deploymentId=...)",
        )

    def _python_function(
        self,
        construct_id: str,
        *,
        function_name: str,
        handler_dir: str,
        layers: list[lambda_.ILayerVersion],
        vpc: ec2.IVpc,
        api_subnets: ec2.SubnetSelection,
        api_lambda_security_group: ec2.ISecurityGroup,
        environment: dict[str, str],
        timeout: Duration = Duration.seconds(29),
    ) -> lambda_.Function:
        return lambda_.Function(
            self,
            construct_id,
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(handler_dir),
            layers=layers,
            timeout=timeout,
            memory_size=512,
            vpc=vpc,
            vpc_subnets=api_subnets,
            security_groups=[api_lambda_security_group],
            environment=environment,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )
