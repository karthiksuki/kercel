import json
import os
from datetime import datetime, timezone

import boto3

dynamo = boto3.resource("dynamodb")

DEPLOYMENTS_TABLE = os.environ["DEPLOYMENTS_TABLE"]
deployments_table = dynamo.Table(DEPLOYMENTS_TABLE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_deployment_status(
    deployment_id: str, created_at: str, status: str, message: str | None = None
) -> None:
    deployments_table.update_item(
        Key={"deploymentId": deployment_id, "createdAt": created_at},
        UpdateExpression="SET #status = :status, updatedAt = :updatedAt, message = :message",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": status,
            ":updatedAt": _now_iso(),
            ":message": message,
        },
    )


def handler(event, context):
    failures = []

    for record in event.get("Records", []):
        try:
            message = json.loads(record["body"])
            print("Processing deployment", message)

            deployment_id = message["deploymentId"]
            created_at = message["createdAt"]

            _set_deployment_status(
                deployment_id, created_at, "building", "Clone and build started"
            )
            _set_deployment_status(
                deployment_id, created_at, "deploying", "Publishing to EC2 hosts"
            )
            _set_deployment_status(
                deployment_id, created_at, "live", "Deployment complete"
            )
        except Exception:
            print("Deployment failed", exc_info=True)
            failures.append({"itemIdentifier": record["messageId"]})

    return {"batchItemFailures": failures}
