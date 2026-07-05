import os
import uuid
from datetime import datetime, timezone

import boto3

from shared.response import json_response

dynamo = boto3.resource("dynamodb")
project_table = dynamo.Table(os.environ["PROJECT_TABLE"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    body = __import__("json").loads(event.get("body") or "{}")
    name = body.get("name")
    github_url = body.get("githubUrl")
    owner_id = body.get("ownerId", "anonymous")

    if not name or not github_url:
        return json_response(400, {"error": "name and githubUrl are required"})

    project_id = str(uuid.uuid4())
    now = _now_iso()
    project = {
        "projectId": project_id,
        "name": name,
        "ownerId": owner_id,
        "githubUrl": github_url,
        "createdAt": now,
        "updatedAt": now,
    }
    project_table.put_item(Item=project)
    return json_response(201, project)
