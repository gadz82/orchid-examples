from __future__ import annotations

from typing import Any


def estimate_construction_cost(building_type: str = "", area_m2: int = 0, quality: str = "medium", **kwargs: Any) -> dict[str, Any]:
    rates: dict[str, dict[str, int]] = {
        "office": {"low": 1800, "medium": 2500, "high": 3500},
        "residential": {"low": 1500, "medium": 2200, "high": 3200},
        "mixed_use": {"low": 2000, "medium": 2800, "high": 4000},
    }
    btype = building_type.lower() if building_type else "office"
    if btype not in rates:
        btype = "office"
    rate = rates[btype].get(quality, 2500)
    total = area_m2 * rate
    return {
        "building_type": btype,
        "quality": quality,
        "area_m2": area_m2,
        "rate_per_m2": rate,
        "total_estimate": total,
        "breakdown": {
            "structure": int(total * 0.30),
            "facade": int(total * 0.18),
            "mechanical": int(total * 0.15),
            "electrical": int(total * 0.10),
            "interior": int(total * 0.15),
            "contingency": int(total * 0.12),
        },
    }


def compare_lifecycle_costs(material: str = "", area_m2: int = 0, **kwargs: Any) -> dict[str, Any]:
    factors: dict[str, dict[str, int]] = {
        "cross-laminated timber": {"initial": 180, "maintenance_annual": 3, "lifespan_years": 60},
        "reinforced concrete": {"initial": 120, "maintenance_annual": 5, "lifespan_years": 100},
        "structural steel": {"initial": 200, "maintenance_annual": 8, "lifespan_years": 80},
        "glulam beams": {"initial": 150, "maintenance_annual": 4, "lifespan_years": 50},
    }
    mat = factors.get(material.lower())
    if not mat:
        return {"error": f"No lifecycle data for '{material}'"}
    init = mat["initial"] * area_m2
    maint = mat["maintenance_annual"] * area_m2 * (mat["lifespan_years"] // 10)
    return {
        "material": material,
        "area_m2": area_m2,
        "initial_cost": init,
        "maintenance_30yr": maint,
        "total_30yr": init + maint,
        "lifespan_years": mat["lifespan_years"],
    }


def get_market_rates(region: str = "", **kwargs: Any) -> dict[str, Any]:
    regions: dict[str, dict[str, Any]] = {
        "london": {"labour_per_hour": 45, "material_multiplier": 1.3, "planning_weeks": 16},
        "berlin": {"labour_per_hour": 38, "material_multiplier": 1.1, "planning_weeks": 12},
        "new york": {"labour_per_hour": 65, "material_multiplier": 1.4, "planning_weeks": 20},
        "tokyo": {"labour_per_hour": 55, "material_multiplier": 1.5, "planning_weeks": 14},
        "paris": {"labour_per_hour": 42, "material_multiplier": 1.2, "planning_weeks": 13},
    }
    r = regions.get(region.lower())
    if not r:
        return {"error": f"No data for region '{region}'", "available_regions": list(regions)}
    return {"region": region, **r}
