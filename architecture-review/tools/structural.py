from __future__ import annotations

from typing import Any

_MATERIALS: dict[str, dict[str, Any]] = {
    "cross-laminated timber": {"strength_mpa": 24, "fire_rating_hours": 2, "carbon_kg_per_m3": -650, "cost_per_m2": 180, "span_limit_m": 12},
    "glulam beams": {"strength_mpa": 28, "fire_rating_hours": 1.5, "carbon_kg_per_m3": -580, "cost_per_m2": 150, "span_limit_m": 30},
    "reinforced concrete": {"strength_mpa": 35, "fire_rating_hours": 4, "carbon_kg_per_m3": 350, "cost_per_m2": 120, "span_limit_m": 15},
    "structural steel": {"strength_mpa": 250, "fire_rating_hours": "1 (unprotected)", "carbon_kg_per_m3": 1850, "cost_per_m2": 200, "span_limit_m": 50},
    "rammed earth": {"strength_mpa": 4, "fire_rating_hours": 4, "carbon_kg_per_m3": 50, "cost_per_m2": 300, "span_limit_m": 4},
    "hempcrete": {"strength_mpa": 1, "fire_rating_hours": 2, "carbon_kg_per_m3": -100, "cost_per_m2": 250, "span_limit_m": 3},
}

_CODES: dict[str, dict[str, Any]] = {
    "eurocode 2": {"jurisdiction": "EU", "material": "concrete", "key_constraints": "minimum cover 25mm, crack control to 0.3mm"},
    "eurocode 3": {"jurisdiction": "EU", "material": "steel", "key_constraints": "slenderness ratio < 180, fatigue assessment for dynamic loads"},
    "eurocode 5": {"jurisdiction": "EU", "material": "timber", "key_constraints": "moisture content < 20%, creep factor 0.6 for indoor"},
    "ibc 2024": {"jurisdiction": "US", "material": "all", "key_constraints": "seismic zone dependant, occupancy category multipliers"},
    "asce 7-22": {"jurisdiction": "US", "material": "all", "key_constraints": "wind speed maps updated, tornado provisions added"},
    "bs 8500": {"jurisdiction": "UK", "material": "concrete", "key_constraints": "exposure class XC3 typical for office, max w/c 0.55"},
}


def analyze_structure(building_type: str = "", floors: int = 0, area_m2: int = 0, **kwargs: Any) -> dict[str, Any]:
    return {
        "building": {"type": building_type or "unspecified", "floors": floors, "area_m2": area_m2},
        "load_estimates": {
            "dead_load_kpa": floors * 7,
            "live_load_kpa": 3 if "office" in building_type.lower() else 5,
            "total_load_kpa": floors * 7 + (3 if "office" in building_type.lower() else 5),
        },
        "recommended_systems": ["steel frame + CLT slabs" if floors > 4 else "CLT + glulam"],
        "span_requirements": {"typical_m": 8, "max_m": 12 if floors > 6 else 10},
    }


def check_code_compliance(jurisdiction: str = "", material: str = "", **kwargs: Any) -> dict[str, Any]:
    applicable = []
    for code_name, code in _CODES.items():
        if jurisdiction.lower() in code["jurisdiction"].lower() or jurisdiction.lower() in code_name.lower():
            if not material or material.lower() in code["material"]:
                applicable.append({"code": code_name, **code})
    return {"jurisdiction": jurisdiction, "material": material, "applicable_codes": applicable, "count": len(applicable)}


def compare_materials(material_a: str = "", material_b: str = "", **kwargs: Any) -> dict[str, Any]:
    a = _MATERIALS.get(material_a.lower())
    b = _MATERIALS.get(material_b.lower())
    if not a or not b:
        return {"error": "Material not found", "available": list(_MATERIALS)}
    return {
        "comparison": {
            material_a: a,
            material_b: b,
            "strength_winner": material_a if a["strength_mpa"] > b["strength_mpa"] else material_b,
            "carbon_winner": material_a if a["carbon_kg_per_m3"] < b["carbon_kg_per_m3"] else material_b,
            "cost_winner": material_a if a["cost_per_m2"] < b["cost_per_m2"] else material_b,
        }
    }


def get_fire_strategy(material: str = "", floors: int = 0, **kwargs: Any) -> dict[str, Any]:
    mat = _MATERIALS.get(material.lower())
    if not mat:
        return {"error": f"Material '{material}' not found"}
    rating = mat["fire_rating_hours"]
    return {
        "material": material,
        "intrinsic_rating_hours": rating,
        "minimum_protection": "none" if (isinstance(rating, int) and rating >= 2) else "intumescent coating or encasement",
        "evacuation_strategy": "defend-in-place" if floors > 6 else "simultaneous evacuation",
        "sprinkler_recommended": floors > 3 or (isinstance(rating, str)),
    }
