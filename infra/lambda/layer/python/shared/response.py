import json
from decimal import Decimal
from typing import Any


def json_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=_serialize),
    }


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, set):
        return list(value)
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")
