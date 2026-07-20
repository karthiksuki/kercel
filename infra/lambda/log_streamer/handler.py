import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamo = boto3.resource("dynamodb")
deploy_act_table = dynamo.Table(os.environ["DEPLOY_ACT_TABLE"])
ws_connections_table = dynamo.Table(os.environ["WS_CONNECTIONS_TABLE"])


def _is_websocket_event(event: dict) -> bool:
    return "requestContext" in event and "routeKey" in event.get("requestContext", {})


def _is_stream_event(event: dict) -> bool:
    return "Records" in event


def _api_client():
    endpoint = os.environ["WEBSOCKET_API_ENDPOINT"]
    return boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)


def _post_to_connection(connection_id: str, data: dict) -> None:
    client = _api_client()
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode("utf-8"),
        )
    except ClientError as err:
        if err.response["Error"]["Code"] == "GoneException":
            ws_connections_table.delete_item(Key={"connectionId": connection_id})
    except Exception:
        pass


def _handle_connect(event: dict) -> dict:
    connection_id = event["requestContext"]["connectionId"]
    params = event.get("queryStringParameters") or {}
    deployment_id = params.get("deploymentId") or params.get("deploymentid")

    if not deployment_id:
        return {"statusCode": 400, "body": "deploymentId query parameter required"}

    ttl = int(time.time()) + 3600
    ws_connections_table.put_item(
        Item={
            "connectionId": connection_id,
            "deploymentId": deployment_id,
            "ttl": ttl,
        }
    )

    # BUG-05 FIX: The original code had Limit=20 with no pagination.
    # For any build that emits more than 20 log actions (which is nearly every
    # real build — install + build alone produce dozens), the newly connected
    # browser would only see the first 20 lines and silently miss everything
    # else.  The fix is a standard DynamoDB pagination loop: keep querying while
    # LastEvaluatedKey is present in the response so we replay *all* existing
    # actions to the client on initial connect.
    #
    # We keep ScanIndexForward=True so actions are replayed in chronological
    # order (oldest first) which matches what the user sees in the terminal UI.
    #
    # NOTE: deploy_act_table PK = deploymentId, SK = actionTimestamp.
    # This query runs on the primary key — no GSI needed, no index/* IAM required.
    exclusive_start_key = None
    while True:
        query_kwargs: dict = {
            "KeyConditionExpression": Key("deploymentId").eq(deployment_id),
            "ScanIndexForward": True,
        }
        if exclusive_start_key:
            query_kwargs["ExclusiveStartKey"] = exclusive_start_key

        actions = deploy_act_table.query(**query_kwargs)
        for action in actions.get("Items", []):
            _post_to_connection(connection_id, {"type": "log", **action})

        exclusive_start_key = actions.get("LastEvaluatedKey")
        if not exclusive_start_key:
            break

    return {"statusCode": 200, "body": "Connected"}


def _handle_disconnect(event: dict) -> dict:
    connection_id = event["requestContext"]["connectionId"]
    ws_connections_table.delete_item(Key={"connectionId": connection_id})
    return {"statusCode": 200, "body": "Disconnected"}


def _handle_stream(event: dict) -> None:
    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue
        image = record.get("dynamodb", {}).get("NewImage", {})
        deployment_id = image.get("deploymentId", {}).get("S")
        if not deployment_id:
            continue

        payload = {
            "type": "log",
            "deploymentId": deployment_id,
            "actionTimestamp": image.get("actionTimestamp", {}).get("S"),
            "action": image.get("action", {}).get("S"),
            "message": image.get("message", {}).get("S"),
        }

        connections = ws_connections_table.query(
            IndexName="byDeploymentId",
            KeyConditionExpression=Key("deploymentId").eq(deployment_id),
        )
        for conn in connections.get("Items", []):
            _post_to_connection(conn["connectionId"], payload)


def handler(event, context):
    if _is_stream_event(event):
        _handle_stream(event)
        return

    if not _is_websocket_event(event):
        return {"statusCode": 400, "body": "Unknown event type"}

    route_key = event["requestContext"]["routeKey"]
    if route_key == "$connect":
        return _handle_connect(event)
    if route_key == "$disconnect":
        return _handle_disconnect(event)
    return {"statusCode": 200, "body": "OK"}
