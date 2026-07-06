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

    actions = deploy_act_table.query(
        KeyConditionExpression=Key("deploymentId").eq(deployment_id),
        ScanIndexForward=True,
        Limit=20,
    )
    for action in actions.get("Items", []):
        _post_to_connection(connection_id, {"type": "log", **action})

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
