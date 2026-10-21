"""Redis caching and distributed coordination client."""
import json
from typing import Optional, Any
import redis.asyncio as aioredis
from app.config import settings
from app.core.logging import logger

try:
    import fakeredis.aioredis as fake_aioredis
except ImportError:
    fake_aioredis = None


class RedisClient:
    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        if settings.USE_FAKE_REDIS:
            if fake_aioredis is not None:
                logger.info("Initializing in-memory FakeRedis client...")
                self._client = fake_aioredis.FakeRedis(decode_responses=True)
            else:
                logger.warning("fakeredis not installed, attempting connection to real Redis")
                self._client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        else:
            try:
                self._client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                await self._client.ping()
                logger.info(f"Connected to Redis at {settings.REDIS_URL}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis at {settings.REDIS_URL}: {e}. Falling back to FakeRedis.")
                if fake_aioredis is not None:
                    self._client = fake_aioredis.FakeRedis(decode_responses=True)
                else:
                    raise

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis client is not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get error for key '{key}': {e}")
            return None

    async def get_json(self, key: str) -> Optional[Any]:
        val = await self.get(key)
        if val:
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return None
        return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        try:
            ttl = ex if ex is not None else settings.CACHE_TTL_SECONDS
            await self.client.set(key, value, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key '{key}': {e}")
            return False

    async def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        try:
            serialized = json.dumps(value)
            return await self.set(key, serialized, ex=ex)
        except Exception as e:
            logger.error(f"Redis set_json error for key '{key}': {e}")
            return False

    async def delete(self, *keys: str) -> int:
        try:
            if not keys:
                return 0
            return await self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete error for keys '{keys}': {e}")
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """Scan and invalidate keys matching a pattern."""
        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = await self.client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await self.client.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception as e:
            logger.error(f"Redis delete_pattern error for pattern '{pattern}': {e}")
            return 0

    async def acquire_lock(self, lock_key: str, owner_id: str, ttl_seconds: int = 10) -> bool:
        """Atomic set-if-not-exists (NX) distributed lock."""
        try:
            result = await self.client.set(f"lock:{lock_key}", owner_id, nx=True, ex=ttl_seconds)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis acquire_lock error for '{lock_key}': {e}")
            return False

    async def release_lock(self, lock_key: str, owner_id: str) -> bool:
        """Safely release lock only if owned by caller."""
        try:
            key = f"lock:{lock_key}"
            val = await self.client.get(key)
            if val == owner_id:
                await self.client.delete(key)
                return True
            return False
        except Exception as e:
            logger.error(f"Redis release_lock error for '{lock_key}': {e}")
            return False


redis_client = RedisClient()
