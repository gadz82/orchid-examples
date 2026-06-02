"""Built-in clothing recommendation tools for the weather example.

Provides outfit recommendations based on weather conditions (temperature,
precipitation, wind, UV index) and activity type.
"""

from __future__ import annotations

from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput


def _clothing_for_temp(temp_c: float, *, precip_pct: int = 0, wind_kmh: float = 0) -> dict[str, list[str]]:
    """Map temperature and conditions to clothing layers."""
    windy = wind_kmh > 30
    rainy = precip_pct > 50

    if temp_c >= 30:
        tops = ["tank top", "light t-shirt", "linen shirt"]
        bottoms = ["shorts", "light skirt", "linen pants"]
        footwear = ["sandals", "flip-flops", "light sneakers"]
        outerwear = ["none — it's hot"] if not rainy else ["light rain jacket"]
        accessories = ["sunglasses", "sun hat", "sunscreen SPF 50+", "water bottle"]
    elif 20 <= temp_c < 30:
        tops = ["t-shirt", "polo shirt", "light blouse"]
        bottoms = ["shorts", "chinos", "midi skirt"]
        footwear = ["sneakers", "loafers", "sandals"]
        outerwear = ["light cardigan for evening"] if not rainy else ["rain jacket"]
        accessories = ["sunglasses", "sunscreen SPF 30+"]
    elif 10 <= temp_c < 20:
        tops = ["long-sleeve shirt", "light sweater", "button-up"]
        bottoms = ["jeans", "chinos", "trousers"]
        footwear = ["sneakers", "loafers", "ankle boots"]
        outerwear = ["light jacket", "denim jacket"] if not rainy else ["waterproof jacket"]
        accessories = ["light scarf (optional)"]
    elif 0 <= temp_c < 10:
        tops = ["thermal base layer", "sweater", "turtleneck"]
        bottoms = ["jeans", "wool trousers", "fleece-lined pants"]
        footwear = ["boots", "waterproof shoes"] if rainy else ["leather boots"]
        outerwear = ["warm coat", "puffer jacket"] if not rainy else ["waterproof winter coat"]
        accessories = ["scarf", "gloves", "beanie"]
    else:
        tops = ["heavy thermal base", "thick sweater", "fleece"]
        bottoms = ["thermal leggings under pants", "insulated snow pants"]
        footwear = ["insulated snow boots", "waterproof winter boots"]
        outerwear = ["heavy parka", "down coat", "windproof shell"]
        accessories = ["thick scarf", "insulated gloves", "wool hat", "hand warmers"]

    if windy and not rainy:
        outerwear.append("windbreaker layer")
        accessories.append("secure loose items — it's windy")

    if rainy:
        accessories.extend(["umbrella", "waterproof bag cover"])
        if temp_c < 15:
            footwear = ["waterproof boots"] if "waterproof" not in str(footwear) else footwear

    return {
        "tops": tops,
        "bottoms": bottoms,
        "footwear": footwear,
        "outerwear": outerwear,
        "accessories": accessories,
    }


def _clothing_for_activity(activity: str, clothes: dict[str, list[str]]) -> dict[str, list[str]]:
    """Adjust clothing recommendations for the activity type."""
    activity = activity.lower().strip()

    if "running" in activity or "jogging" in activity or "workout" in activity or "gym" in activity:
        clothes["tops"] = ["moisture-wicking athletic shirt"] + clothes["tops"]
        clothes["bottoms"] = ["athletic shorts", "running tights"]
        clothes["footwear"] = ["running shoes", "training shoes"]
    elif "hiking" in activity or "trail" in activity or "outdoor" in activity:
        clothes["footwear"] = ["hiking boots", "trail shoes"] + clothes["footwear"]
        clothes["accessories"].append("backpack with water and snacks")
    elif "business" in activity or "office" in activity or "formal" in activity or "work" in activity:
        clothes["tops"] = ["dress shirt", "blazer-ready top"]
        clothes["bottoms"] = ["dress pants", "tailored trousers"]
        clothes["footwear"] = ["dress shoes", "formal boots"]
    elif "beach" in activity or "swim" in activity or "pool" in activity:
        clothes["tops"] = ["swim top", "tank top"]
        clothes["bottoms"] = ["swim shorts", "board shorts"]
        clothes["footwear"] = ["flip-flops", "water shoes"]
        clothes["accessories"].extend(["beach towel", "sunscreen SPF 50+"])

    return clothes


class RecommendOutfitTool(OrchidTool):
    """Recommend outfits based on weather conditions and activity."""

    name = "recommend_outfit"
    description = (
        "Recommend clothing and outfit combinations based on weather conditions "
        "(temperature, precipitation, wind, UV index) and activity type. "
        "Returns layered outfit suggestions with reasoning."
    )

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        params = tool_input.parameters
        temp_c = params.get("temperature_c", params.get("temperature", 20))
        precip_pct = params.get("precipitation_chance", params.get("precip_pct", 0))
        wind_kmh = params.get("wind_speed_kmh", params.get("wind_kmh", 0))
        uv_index = params.get("uv_index", 0)
        activity = params.get("activity", "casual")

        try:
            temp_c = float(temp_c)
            precip_pct = int(precip_pct)
            wind_kmh = float(wind_kmh)
            uv_index = float(uv_index)
        except (ValueError, TypeError):
            return OrchidToolOutput(metadata={"error": "Invalid numeric values for weather parameters."})

        clothes = _clothing_for_temp(temp_c, precip_pct=precip_pct, wind_kmh=wind_kmh)
        clothes = _clothing_for_activity(activity, clothes)

        # UV-specific additions
        if uv_index > 6:
            clothes["accessories"].extend(["high-SPF sunscreen", "UV-protective sunglasses"])
            if "sunglasses" not in str(clothes["accessories"]):
                clothes["accessories"].append("sunglasses")

        # Build the result
        conditions = f"{temp_c}°C"
        if precip_pct > 0:
            conditions += f", {precip_pct}% rain chance"
        if wind_kmh > 0:
            conditions += f", {wind_kmh} km/h wind"
        if uv_index > 0:
            conditions += f", UV {uv_index}"

        result: dict[str, Any] = {
            "conditions": conditions,
            "activity": activity,
            "outfit": {k: v for k, v in clothes.items()},
        }

        return OrchidToolOutput(result=result)
