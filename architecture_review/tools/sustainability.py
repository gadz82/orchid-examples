from __future__ import annotations

from typing import Any

_CERTIFICATIONS: dict[str, dict[str, Any]] = {
    "breeam": {"levels": ["Pass", "Good", "Very Good", "Excellent", "Outstanding"], "focus": "Europe", "key_categories": ["Energy", "Water", "Materials", "Ecology", "Pollution"]},
    "leed": {"levels": ["Certified", "Silver", "Gold", "Platinum"], "focus": "North America", "key_categories": ["Energy & Atmosphere", "Materials", "Indoor Quality", "Water", "Location"]},
    "dgnb": {"levels": ["Bronze", "Silver", "Gold", "Platinum"], "focus": "Germany / EU", "key_categories": ["LCA", "Economic Quality", "Sociocultural Quality", "Technical Quality"]},
    "well": {"levels": ["Silver", "Gold", "Platinum"], "focus": "Global", "key_categories": ["Air", "Water", "Light", "Comfort", "Mind", "Nourishment"]},
}

_MATERIAL_CARBON: dict[str, dict[str, Any]] = {
    "cross-laminated timber": {"embodied_kgco2_per_m3": 110, "biogenic_kgco2_per_m3": -760, "recyclable": True, "epd_certified": True},
    "reinforced concrete": {"embodied_kgco2_per_m3": 350, "biogenic_kgco2_per_m3": 0, "recyclable": "crushed aggregate only", "epd_certified": True},
    "structural steel": {"embodied_kgco2_per_m3": 1850, "biogenic_kgco2_per_m3": 0, "recyclable": True, "epd_certified": True},
    "glulam beams": {"embodied_kgco2_per_m3": 130, "biogenic_kgco2_per_m3": -580, "recyclable": False, "epd_certified": True},
    "rammed earth": {"embodied_kgco2_per_m3": 50, "biogenic_kgco2_per_m3": 0, "recyclable": True, "epd_certified": False},
}

_STRATEGIES: list[dict[str, Any]] = [
    {"name": "Passive ventilation", "savings_percent": 25, "applicable_to": "all", "upfront_cost": "low"},
    {"name": "Green roof (extensive)", "savings_percent": 10, "applicable_to": "low-rise", "upfront_cost": "medium"},
    {"name": "Triple glazing + thermal break", "savings_percent": 30, "applicable_to": "all", "upfront_cost": "high"},
    {"name": "Solar PV (roof-mounted)", "savings_percent": 40, "applicable_to": "flat/south-facing roof", "upfront_cost": "high"},
    {"name": "Ground-source heat pump", "savings_percent": 50, "applicable_to": "site with borehole access", "upfront_cost": "high"},
    {"name": "Rainwater harvesting", "savings_percent": 30, "applicable_to": "all", "upfront_cost": "medium"},
    {"name": "Dynamic solar shading", "savings_percent": 15, "applicable_to": "south/west facades", "upfront_cost": "medium"},
]


def evaluate_certification(certification: str = "", target_level: str = "", area_m2: int = 0, **kwargs: Any) -> dict[str, Any]:
    cert = _CERTIFICATIONS.get(certification.lower())
    if not cert:
        return {"error": f"'{certification}' not found", "available": list(_CERTIFICATIONS)}
    return {
        "certification": certification.upper(),
        "available_levels": cert["levels"],
        "target": target_level or cert["levels"][0],
        "focus_region": cert["focus"],
        "key_categories": cert["key_categories"],
        "estimated_cost": area_m2 * 15 if certification.lower() in ("breeam", "dgnb") else area_m2 * 12,
        "estimated_timeline_weeks": 20 if target_level and target_level.lower() == cert["levels"][-1].lower() else 12,
    }


def calculate_embodied_carbon(material: str = "", volume_m3: int = 0, **kwargs: Any) -> dict[str, Any]:
    mat = _MATERIAL_CARBON.get(material.lower())
    if not mat:
        return {"error": f"No carbon data for '{material}'", "available_materials": list(_MATERIAL_CARBON)}
    embodied = mat["embodied_kgco2_per_m3"] * volume_m3
    biogenic = mat["biogenic_kgco2_per_m3"] * volume_m3 if mat["biogenic_kgco2_per_m3"] else 0
    return {
        "material": material,
        "volume_m3": volume_m3,
        "embodied_kgco2": embodied,
        "biogenic_kgco2": biogenic,
        "net_kgco2": embodied + biogenic,
        "epd_certified": mat["epd_certified"],
        "recyclability": mat["recyclable"],
    }


def get_sustainability_strategies(building_type: str = "", climate_zone: str = "", **kwargs: Any) -> dict[str, Any]:
    applicable = []
    for s in _STRATEGIES:
        if s["applicable_to"] == "all" or building_type.lower() in s["applicable_to"]:
            applicable.append(s)
    return {
        "building_type": building_type,
        "climate_zone": climate_zone,
        "recommended_strategies": applicable,
        "estimated_combined_savings_percent": sum(s["savings_percent"] for s in applicable[:3]) // len(applicable[:3]) if applicable else 0,
    }


def compare_carbon_footprints(options: str = "", **kwargs: Any) -> dict[str, Any]:
    results = {}
    for opt in options.split(","):
        opt = opt.strip()
        if not opt:
            continue
        parts = opt.rsplit(" ", 1)
        mat = parts[0].strip()
        try:
            vol = int(parts[1])
        except (IndexError, ValueError):
            vol = 100
        carbon = _MATERIAL_CARBON.get(mat.lower())
        if carbon:
            results[mat] = {
                "volume_m3": vol,
                "embodied_kgco2": carbon["embodied_kgco2_per_m3"] * vol,
                "biogenic_kgco2": carbon["biogenic_kgco2_per_m3"] * vol,
                "net_kgco2": (carbon["embodied_kgco2_per_m3"] + carbon["biogenic_kgco2_per_m3"]) * vol,
            }
    if not results:
        return {"error": "No valid material-volume pairs provided", "format": "material1 100, material2 200"}
    return {"comparison": results, "winner": min(results.items(), key=lambda x: x[1]["net_kgco2"])[0]}
