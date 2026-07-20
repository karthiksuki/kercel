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

    # BUG-06 FIX: The original code auto-created a phantom user record for any
    # unknown userId and returned 200 OK. This had two problems:
    #
    # 1. Any anonymous caller could pollute the users table by GETting arbitrary
    #    UUIDs — the table would fill with fake "@placeholder.kercel.dev" records.
    # 2. It masked the real 404 condition, making the API misleading (a GET
    #    should never silently mutate state).
    #
    # Correct behaviour: if the user does not exist, return 404 and do nothing.
    if "Item" not in result:
        return json_response(404, {"error": "User not found"})

    item = result["Item"]
    cache_set(cache_key, item)
    return json_response(200, item)
