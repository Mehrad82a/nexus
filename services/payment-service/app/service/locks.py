import uuid
from contextlib import contextmanager
import redis
from fastapi import HTTPException, status

from app.core.config import settings



_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=settings.redis_db,
        decode_responses=True,
    )



@contextmanager
def redis_distributed_lock(lock_name: str, *, ttl_seconds: int = 15):
    """
    Acquire a Redis distributed lock using atomic SET NX EX.
    Raises HTTP 409 Conflict if the lock is already held by another concurrent process.
    """
    client = get_redis_client()
    lock_key = f'nexus:payment:lock:{lock_name}'
    token = str(uuid.uuid4())

    acquired = client.set(lock_key, token, nx=True, ex=ttl_seconds)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Another payment operation is currently in progress for this order.'
        )


    try:
        yield token
    finally:
        try:
            client.eval(_RELEASE_LOCK_LUA, 1, lock_key, token)
        except Exception:
            pass


