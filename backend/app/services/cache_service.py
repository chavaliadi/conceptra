import os
import json
import logging
import redis.asyncio as redis
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_client: Optional[redis.Redis] = None

async def init_redis() -> None:
    global redis_client
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Connected to Redis successfully!")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        redis_client = None

async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.aclose()
        logger.info("Redis connection closed.")

def _make_key(topic: str, num_concepts: int) -> str:
    # Clean topic string for slug
    slug = "".join(c if c.isalnum() else "_" for c in topic.strip().lower())
    slug = "_".join(filter(None, slug.split("_")))
    return f"plan:{slug}:{num_concepts}"

async def get_plan_cache(topic: str, num_concepts: int) -> Optional[dict]:
    if not redis_client:
        return None
    key = _make_key(topic, num_concepts)
    try:
        val = await redis_client.get(key)
        if val:
            logger.info(f"Redis cache hit for key: {key}")
            return json.loads(val)
    except Exception as e:
        logger.warning(f"Failed to read from Redis cache: {e}")
    return None

async def set_plan_cache(topic: str, num_concepts: int, data: dict, ttl: int = 604800) -> None:
    if not redis_client:
        return
    key = _make_key(topic, num_concepts)
    try:
        await redis_client.set(key, json.dumps(data), ex=ttl)
        logger.info(f"Stored plan in Redis cache under key: {key}")
    except Exception as e:
        logger.warning(f"Failed to write to Redis cache: {e}")
