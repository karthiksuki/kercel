import os
from datetime import datetime, timezone

import boto3

from shared.redis_cache import cache_get, cache_set
from shared.response import json_response

dynamo = boto3.resource("dynamodb")
user_table = dynamo.Table(os.environ["USER_TABLE"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    user_id = (event.get("pathParameters") or {}).get("id")
    if not user_id:
        return json_response(400, {"error": "user id is required"})

    cache_key = f"user:{user_id}"
    cached = cache_get(cache_key)
    if cached:
        return json_response(200, cached)

    result = user_table.get_item(Key={"userId": user_id})
    if "Item" not in result:
        placeholder = {
            "userId": user_id,
            "email": f"{user_id}@placeholder.kercel.dev",
            "createdAt": _now_iso(),
        }
        user_table.put_item(Item=placeholder)
        cache_set(cache_key, placeholder)
        return json_response(200, placeholder)

    cache_set(cache_key, result["Item"])
    return json_response(200, result["Item"])
