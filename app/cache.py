"""
Session memory and spatial query caching layer for ORCA backend.
Implements async Redis with an in-memory TTL fallback.
Provides spatial coordinate quantization and hit-ratio telemetry.
"""

import json
import time
import asyncio
from typing import Optional, Any, Dict
from app.config import settings

# In-memory TTL fallback storage
_memory_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = asyncio.Lock()

# Cache telemetry stats
_cache_stats = {
    "hits": 0,
    "misses": 0
}


class SpatialCache:
    def __init__(self):
        self.redis_client = None
        self._connected = False
        self._init_attempted = False

    async def _get_redis(self):
        if not settings.CACHE_ENABLED:
            return None
        if not self._init_attempted:
            self._init_attempted = True
            try:
                import redis.asyncio as aioredis
                self.redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=1.5
                )
                await self.redis_client.ping()
                self._connected = True
            except Exception:
                self.redis_client = None
                self._connected = False
        return self.redis_client if self._connected else None

    @staticmethod
    def get_spatial_key(
        namespace: str,
        lat: float,
        lon: float,
        species: Optional[str] = None,
        lang: str = "en"
    ) -> str:
        """
        Quantizes coordinates to SPATIAL_CACHE_PRECISION decimal places (~1.1km)
        to optimize cache hit ratios for marine queries in the same fishing ground.
        """
        precision = settings.SPATIAL_CACHE_PRECISION
        quant_lat = round(lat, precision)
        quant_lon = round(lon, precision)
        clean_species = (species or "any").lower().strip()
        clean_lang = (lang or "en").lower().strip()
        return f"orca:{namespace}:{quant_lat}:{quant_lon}:{clean_species}:{clean_lang}"

    @classmethod
    def get_advisory_key(cls, lat: float, lon: float, species: Optional[str] = None, lang: str = "en") -> str:
        return cls.get_spatial_key("advisory", lat, lon, species, lang)

    @classmethod
    def get_ocean_key(cls, lat: float, lon: float, species: Optional[str] = None) -> str:
        return cls.get_spatial_key("ocean", lat, lon, species, "default")

    @classmethod
    def get_weather_key(cls, lat: float, lon: float) -> str:
        return cls.get_spatial_key("weather", lat, lon, "default", "default")

    @classmethod
    def get_geofence_key(cls, lat: float, lon: float) -> str:
        return cls.get_spatial_key("geofence", lat, lon, "default", "default")

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        if not settings.CACHE_ENABLED:
            return None

        # 1. Try Redis first
        try:
            r = await self._get_redis()
            if r:
                data = await r.get(key)
                if data:
                    _cache_stats["hits"] += 1
                    return json.loads(data)
        except Exception:
            self._connected = False

        # 2. In-memory fallback
        async with _cache_lock:
            entry = _memory_cache.get(key)
            if entry:
                if entry["expires_at"] > time.time():
                    _cache_stats["hits"] += 1
                    return entry["data"]
                else:
                    del _memory_cache[key]

        _cache_stats["misses"] += 1
        return None

    async def set(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        if not settings.CACHE_ENABLED:
            return

        ttl = ttl_seconds or settings.CACHE_TTL_SECONDS
        json_val = json.dumps(value, default=str)

        # 1. Try Redis
        try:
            r = await self._get_redis()
            if r:
                await r.setex(key, ttl, json_val)
                return
        except Exception:
            self._connected = False

        # 2. In-memory fallback
        async with _cache_lock:
            # Evict expired keys or least recently added if memory cache grows over 1000 items
            if len(_memory_cache) > 1000:
                now = time.time()
                keys_to_remove = [k for k, v in _memory_cache.items() if v["expires_at"] <= now]
                for k in keys_to_remove:
                    del _memory_cache[k]
                if len(_memory_cache) > 1000:
                    oldest = min(_memory_cache.keys(), key=lambda k: _memory_cache[k]["expires_at"])
                    del _memory_cache[oldest]

            _memory_cache[key] = {
                "data": value,
                "expires_at": time.time() + ttl
            }

    async def clear(self) -> int:
        """Clears both Redis and in-memory cache."""
        count = 0
        try:
            r = await self._get_redis()
            if r:
                keys = await r.keys("orca:*")
                if keys:
                    count += await r.delete(*keys)
        except Exception:
            self._connected = False

        async with _cache_lock:
            count += len(_memory_cache)
            _memory_cache.clear()

        _cache_stats["hits"] = 0
        _cache_stats["misses"] = 0
        return count

    async def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry stats."""
        total = _cache_stats["hits"] + _cache_stats["misses"]
        hit_ratio = round((_cache_stats["hits"] / total * 100), 2) if total > 0 else 0.0
        redis_conn = await self.is_connected()

        async with _cache_lock:
            mem_count = len(_memory_cache)

        return {
            "cache_enabled": settings.CACHE_ENABLED,
            "backend": "redis" if redis_conn else "in-memory-fallback",
            "hits": _cache_stats["hits"],
            "misses": _cache_stats["misses"],
            "hit_ratio_percent": hit_ratio,
            "in_memory_keys_count": mem_count,
            "redis_connected": redis_conn
        }

    async def is_connected(self) -> bool:
        r = await self._get_redis()
        return bool(r and self._connected)


cache = SpatialCache()
