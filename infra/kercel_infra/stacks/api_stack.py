from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticache as elasticache
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from kercel_infra.constructs.api import ApiConstruct


class ApiStack(Stack):
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
        redis_cluster: elasticache.CfnCacheCluster,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        api = ApiConstruct(
            self,
            "Api",
            stage=stage,
            vpc=vpc,
            api_lambda_security_group=api_lambda_security_group,
            user_table=user_table,
            project_table=project_table,
            history_table=history_table,
            deploy_act_table=deploy_act_table,
            ws_connections_table=ws_connections_table,
            deployment_queue=deployment_queue,
            redis_endpoint=redis_cluster.attr_redis_endpoint_address,
            redis_port=redis_cluster.attr_redis_endpoint_port,
        )

        self.rest_api = api.rest_api
        self.websocket_api = api.websocket_api
