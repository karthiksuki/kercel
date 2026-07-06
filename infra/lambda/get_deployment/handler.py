import os

import boto3
from boto3.dynamodb.conditions import Key

from shared.redis_cache import cache_get, cache_set
from shared.response import json_response

dynamo = boto3.resource("dynamodb")
history_table = dynamo.Table(os.environ["HISTORY_TABLE"])
deploy_act_table = dynamo.Table(os.environ["DEPLOY_ACT_TABLE"])


def handler(event, context):
    deployment_id = (event.get("pathParameters") or {}).get("id")
    if not deployment_id:
        return json_response(400, {"error": "deployment id is required"})

    cache_key = f"deployment:{deployment_id}"
    cached = cache_get(cache_key)
    if cached:
        return json_response(200, cached)

    history_result = history_table.query(
        IndexName="byDeploymentId",
        KeyConditionExpression=Key("deploymentId").eq(deployment_id),
        Limit=1,
    )
    history_items = history_result.get("Items", [])
    if not history_items:
        return json_response(404, {"error": "Deployment not found"})

    history = history_items[0]
    actions_result = deploy_act_table.query(
        KeyConditionExpression=Key("deploymentId").eq(deployment_id),
        ScanIndexForward=True,
        Limit=50,
    )

    response = {
        **history,
        "actions": actions_result.get("Items", []),
    }
    cache_set(cache_key, response, ttl_seconds=30)
    return json_response(200, response)
