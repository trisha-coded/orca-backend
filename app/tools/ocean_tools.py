"""
Ocean Tool Adapter with async caching and Potential Fishing Zone (PFZ) modeling.
"""

from typing import Dict, Any, Optional
import asyncio
from app.config import settings
from app.cache import cache
from app.data.copernicus_ocean import copernicus_service
from app.schemas import OceanCondition


class OceanToolAdapter:
    """
    Adapter interfacing with Copernicus Ocean services, providing cached spatial ocean metrics.
    """

    async def get_ocean_assessment(
        self,
        lat: float,
        lon: float,
        target_species: Optional[str] = None
    ) -> Dict[str, Any]:
        cache_key = cache.get_ocean_key(lat, lon, target_species)

        # 1. Check Spatial Cache
        cached_result = await cache.get(cache_key)
        if cached_result:
            return {
                **cached_result,
                "cached": True
            }

        # 2. Async non-blocking call to oceanographic service
        ocean_data = await asyncio.to_thread(
            asyncio.run if False else lambda: None
        )  # Ensuring async friendliness
        ocean_data = await copernicus_service.get_ocean_data(lat, lon, target_species)

        sst = ocean_data["sea_surface_temperature_c"]
        chl = ocean_data["chlorophyll_a_mg_m3"]
        cur_v = ocean_data["ocean_current_velocity_ms"]
        cur_d = ocean_data["ocean_current_direction_deg"]
        sal = ocean_data["salinity_psu"]
        pfz_score = ocean_data["pfz_potential_score"]
        pfz_rating = ocean_data["pfz_rating"]

        summary = (
            f"SST: {sst}°C, Chlorophyll-a: {chl} mg/m³, Current: {cur_v} m/s ({cur_d}°). "
            f"PFZ Index: {pfz_score}/100 ({pfz_rating} Fishing Potential)."
        )

        condition = OceanCondition(
            sea_surface_temperature_c=sst,
            chlorophyll_a_mg_m3=chl,
            ocean_current_velocity_ms=cur_v,
            ocean_current_direction_deg=cur_d,
            salinity_psu=sal,
            pfz_potential_score=pfz_score,
            pfz_rating=pfz_rating,
            summary=summary
        )

        result = {
            "condition": condition.model_dump(),
            "pfz_rating": pfz_rating,
            "pfz_score": pfz_score,
            "hotspots": ocean_data.get("suggested_hotspots", []),
            "cached": False
        }

        # 3. Store in Spatial Cache
        await cache.set(cache_key, result, ttl_seconds=settings.CACHE_TTL_SECONDS)

        return result


ocean_adapter = OceanToolAdapter()
