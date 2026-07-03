import json
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import boto3

dynamo = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

PROJECTS_TABLE = os.environ["PROJECTS_TABLE"]
DEPLOYMENTS_TABLE = os.environ["DEPLOYMENTS_TABLE"]
DEPLOYMENT_QUEUE_URL = os.environ["DEPLOYMENT_QUEUE_URL"]

projects_table = dynamo.Table(PROJECTS_TABLE)
deployments_table = dynamo.Table(DEPLOYMENTS_TABLE)


def _json_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def _parse_github_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        if parsed.hostname not in ("github.com", "www.github.com"):
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None
        return f"https://github.com/{parts[0]}/{parts[1]}"
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    try:
        method = event.get("httpMethod", "")
        path = event.get("path", "/")
        body = json.loads(event.get("body") or "{}")
        path_params = event.get("pathParameters") or {}

        if method == "POST" and path.endswith("/projects"):
            github_url = _parse_github_url(body.get("githubUrl", ""))
            if not github_url:
                return _json_response(
                    400, {"error": "githubUrl must be a valid GitHub repository URL"}
                )

            now = _now_iso()
            project = {
                "projectId": str(uuid.uuid4()),
                "githubUrl": github_url,
                "name": body.get("name") or github_url.rstrip("/").split("/")[-1],
                "createdAt": now,
                "updatedAt": now,
            }
            projects_table.put_item(Item=project)
            return _json_response(201, project)

        if method == "GET" and path.endswith("/projects") and not path_params.get("projectId"):
            result = projects_table.scan(Limit=50)
            return _json_response(200, {"projects": result.get("Items", [])})

        project_id = path_params.get("projectId")
        if not project_id:
            return _json_response(404, {"error": "Not found"})

        if method == "GET" and path.endswith(f"/projects/{project_id}"):
            result = projects_table.get_item(Key={"projectId": project_id})
            if "Item" not in result:
                return _json_response(404, {"error": "Project not found"})
            return _json_response(200, result["Item"])

        if method == "POST" and "/deployments" in path:
            project = projects_table.get_item(Key={"projectId": project_id})
            if "Item" not in project:
                return _json_response(404, {"error": "Project not found"})

            now = _now_iso()
            deployment = {
                "deploymentId": str(uuid.uuid4()),
                "projectId": project_id,
                "githubUrl": project["Item"]["githubUrl"],
                "status": "queued",
                "createdAt": now,
                "updatedAt": now,
            }
            deployments_table.put_item(Item=deployment)

            sqs.send_message(
                QueueUrl=DEPLOYMENT_QUEUE_URL,
                MessageBody=json.dumps(
                    {
                        "deploymentId": deployment["deploymentId"],
                        "projectId": project_id,
                        "githubUrl": deployment["githubUrl"],
                        "createdAt": deployment["createdAt"],
                    }
                ),
            )
            return _json_response(202, deployment)

        if method == "GET" and path.endswith("/deployments"):
            result = deployments_table.query(
                IndexName="byProjectId",
                KeyConditionExpression="projectId = :projectId",
                ExpressionAttributeValues={":projectId": project_id},
                ScanIndexForward=False,
                Limit=25,
            )
            return _json_response(200, {"deployments": result.get("Items", [])})

        deployment_id = path_params.get("deploymentId")
        if method == "GET" and deployment_id:
            result = deployments_table.query(
                KeyConditionExpression="deploymentId = :deploymentId",
                ExpressionAttributeValues={":deploymentId": deployment_id},
                Limit=1,
            )
            items = result.get("Items", [])
            if not items:
                return _json_response(404, {"error": "Deployment not found"})
            return _json_response(200, items[0])

        return _json_response(404, {"error": "Not found"})
    except Exception:
        print("API handler error", exc_info=True)
        return _json_response(500, {"error": "Internal server error"})
