import json
import os
import uuid
from datetime import datetime, timezone

import boto3

from shared.response import json_response

dynamo = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

project_table = dynamo.Table(os.environ["PROJECT_TABLE"])
history_table = dynamo.Table(os.environ["HISTORY_TABLE"])
deploy_act_table = dynamo.Table(os.environ["DEPLOY_ACT_TABLE"])
deployment_queue_url = os.environ["DEPLOYMENT_QUEUE_URL"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    body = json.loads(event.get("body") or "{}")
    project_id = body.get("projectId")
    user_id = body.get("userId")

    if not project_id:
        return json_response(400, {"error": "projectId required"})

    project = project_table.get_item(Key={"projectId": project_id})
    if "Item" not in project:
        return json_response(404, {"error": "Project not found"})

    item = project["Item"]
    deployment_id = str(uuid.uuid4())
    now = _now_iso()
    resolved_user = user_id or item.get("ownerId", "anonymous")

    history_table.put_item(
        Item={
            "projectId": project_id,
            "deploymentId": deployment_id,
            "status": "queued",
            "createdAt": now,
            "userId": resolved_user,
            "githubUrl": item["githubUrl"],
        }
    )

    deploy_act_table.put_item(
        Item={
            "deploymentId": deployment_id,
            "actionTimestamp": now,
            "action": "QUEUED",
            "message": "Deployment queued",
        }
    )

    sqs.send_message(
        QueueUrl=deployment_queue_url,
        MessageBody=json.dumps(
            {
                "deploymentId": deployment_id,
                "projectId": project_id,
                "userId": resolved_user,
                "githubUrl": item["githubUrl"],
                "createdAt": now,
            }
        ),
    )

    return json_response(
        202,
        {"deploymentId": deployment_id, "projectId": project_id, "status": "queued"},
    )
