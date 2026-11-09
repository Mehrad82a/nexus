import uuid
from contextlib import contextmanager
from django_redis import get_redis_connection
from rest_framework.exceptions import APIException



class DistributedLockConflictError(APIException):
    status_code = 409
    default_detail = 'Another operation is currently in progress for this resource. Please retry.'
    default_code = 'lock_conflict'



# Lua script ensures we only delete the lock if we still own the token
_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


@contextmanager
def redis_distributed_lock(lock_name: str, *, ttl_seconds: int = 15):
    """
    Acquire a Redis distributed lock using atomic SET NX EX.
    Raises HTTP 409 Conflict if the lock is already held by another concurrent process.
    """
    redis_conn = get_redis_connection('default')
    lock_key = f'nexus:order:lock:{lock_name}'
    token = str(uuid.uuid4())

    acquired = redis_conn.set(lock_key, token, nx=True, ex=ttl_seconds)
    if not acquired:
        raise DistributedLockConflictError()


    try:
        yield token

    finally:
        try:
            redis_conn.eval(_RELEASE_LOCK_LUA, 1, lock_key, token)
        except Exception:
            pass




