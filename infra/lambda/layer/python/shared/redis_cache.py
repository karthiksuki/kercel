import json
import os
from typing import Any

_redis_client = None


def _get_client():
    global _redis_client
    host = os.environ.get("REDIS_HOST")
    if not host:
        return None
    if _redis_client is None:
        try:
            import redis 

            port = int(os.environ.get("REDIS_PORT", "6379"))
            _redis_client = redis.Redis(
                host=host,
                port=port,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception:
            return None
    return _redis_client


def cache_get(key: str) -> dict[str, Any] | None:
    client = _get_client()
    if not client:
        return None
    try:
        value = client.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def cache_set(key: str, value: dict[str, Any], ttl_seconds: int = 300) -> None:
    client = _get_client()
    if not client:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(value))
    except Exception:
        pass
