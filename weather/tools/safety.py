"""Built-in safety recommendation tools for the weather example.

Provides safety tips and risk assessment for extreme weather conditions.
"""

from __future__ import annotations

from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

_SAFETY_GUIDES: dict[str, dict[str, list[str]]] = {
    "heatwave": {
        "immediate": [
            "Stay indoors in air-conditioned spaces during peak heat (11am-4pm)",
            "Drink water regularly — don't wait until you're thirsty",
            "Avoid strenuous outdoor activities",
            "Never leave children or pets in parked vehicles",
        ],
        "preparation": [
            "Check on elderly neighbours and vulnerable family members",
            "Close curtains and blinds on sun-facing windows",
            "Use fans with a bowl of ice for evaporative cooling",
            "Identify nearby cooling centres or public air-conditioned spaces",
        ],
        "signs_of_distress": [
            "Heat exhaustion: heavy sweating, weakness, nausea, headache",
            "Heat stroke: hot/dry skin, confusion, loss of consciousness — CALL EMERGENCY SERVICES",
        ],
    },
    "extreme_cold": {
        "immediate": [
            "Stay indoors and keep warm",
            "Layer clothing: base layer (moisture-wicking), mid layer (insulation), outer layer (wind/waterproof)",
            "Cover extremities: wear hat, scarf, gloves, warm socks",
            "Limit time outdoors to less than 15-20 minutes",
        ],
        "preparation": [
            "Insulate pipes to prevent freezing",
            "Keep emergency heating source (safe indoor heater, extra blankets)",
            "Stock emergency food and water for 3+ days",
            "Keep phones charged and have a battery-powered radio",
        ],
        "signs_of_distress": [
            "Frostbite: numbness, white/greyish skin, firm/waxy feel — warm gradually, seek medical help",
            "Hypothermia: shivering, confusion, drowsiness, slurred speech — CALL EMERGENCY SERVICES",
        ],
    },
    "storm": {
        "immediate": [
            "Seek shelter indoors, away from windows",
            "Avoid using corded phones and electrical appliances",
            "Stay away from plumbing (sinks, baths) during lightning",
            "If driving, pull over safely, avoid trees and power lines",
        ],
        "preparation": [
            "Secure outdoor furniture and loose items",
            "Charge devices and have power banks ready",
            "Keep flashlights and batteries accessible",
            "Know how to manually open garage doors",
        ],
        "signs_of_distress": [
            "Flooding: move to higher ground, never walk or drive through flood water",
            "Downed power lines: stay at least 10m away, report immediately",
        ],
    },
    "flood": {
        "immediate": [
            "Move to higher ground immediately",
            "NEVER walk, swim, or drive through flood waters — 15cm of water can knock you down",
            "Avoid contact with flood water (contamination, debris, hidden hazards)",
            "Disconnect electrical appliances if safe to do so",
        ],
        "preparation": [
            "Know your evacuation route and meeting point",
            "Prepare a go-bag: documents, medications, water, non-perishable food, flashlight, batteries",
            "Move valuables to upper floors",
            "Sandbag doorways and low openings",
        ],
        "signs_of_distress": [
            "Rapidly rising water: evacuate immediately, don't wait for official notice",
            "Muddy or debris-filled water indicates upstream flooding",
        ],
    },
    "blizzard": {
        "immediate": [
            "Stay indoors — whiteout conditions make travel extremely dangerous",
            "Keep all doors and windows closed",
            "Run water at a trickle to prevent pipe freezing",
            "Use safe heating — never use outdoor grills or generators indoors",
        ],
        "preparation": [
            "Stock 3+ days of food, water, and medications",
            "Have snow shovels and ice melt ready",
            "Keep vehicles full of fuel",
            "Have emergency blankets and warm clothing accessible",
        ],
        "signs_of_distress": [
            "Carbon monoxide poisoning: headache, dizziness, nausea — ventilate and seek fresh air immediately",
        ],
    },
    "hurricane": {
        "immediate": [
            "Evacuate if ordered by authorities — do not wait",
            "If staying, shelter in an interior room without windows",
            "Fill bathtub and containers with water for sanitation",
            "Turn off propane tanks and secure loose outdoor items",
        ],
        "preparation": [
            "Board up windows or install storm shutters",
            "Prepare emergency kit: water (1 gallon/person/day, 3+ days), food, medications, documents",
            "Fill vehicles with fuel, have cash on hand",
            "Know your evacuation zone and route",
        ],
        "signs_of_distress": [
            "Eye of the storm: temporary calm does NOT mean it's over — stay sheltered",
            "Storm surge: the leading cause of hurricane deaths — evacuate coastal areas immediately",
        ],
    },
}


class GetSafetyTipsTool(OrchidTool):
    """Get safety recommendations for specific weather hazards."""

    name = "get_safety_tips"
    description = (
        "Get safety recommendations and preparedness tips for specific weather hazards "
        "(heatwaves, storms, floods, blizzards, hurricanes, extreme cold). "
        "Returns actionable safety guidance with immediate actions, preparation tips, "
        "and warning signs."
    )

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        hazard = (tool_input.parameters.get("hazard") or tool_input.parameters.get("hazard_type") or "").lower().strip()

        guide = _SAFETY_GUIDES.get(hazard)
        if guide is None:
            available = ", ".join(sorted(_SAFETY_GUIDES.keys()))
            return OrchidToolOutput(metadata={"error": f"Unknown hazard '{hazard}'. Available: {available}"})

        return OrchidToolOutput(result={
            "hazard": hazard,
            "recommendations": guide,
        })


class AssessWeatherRiskTool(OrchidTool):
    """Assess the risk level of weather conditions."""

    name = "assess_weather_risk"
    description = (
        "Assess the risk level (low/moderate/high/extreme) of current or forecasted "
        "weather conditions. Considers temperature extremes, wind speeds, precipitation "
        "intensity, and storm risk."
    )

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        params = tool_input.parameters
        temp_c = float(params.get("temperature_c", params.get("temperature", 20)))
        wind_kmh = float(params.get("wind_speed_kmh", params.get("wind_kmh", 0)))
        precip_mm = float(params.get("precipitation_mm", params.get("rain_mm", 0)))
        weather_code = params.get("weather_code", params.get("condition", ""))

        risks: list[dict[str, Any]] = []
        overall = "low"

        # Temperature risks
        if temp_c >= 40:
            risks.append({"hazard": "extreme_heat", "level": "extreme", "detail": f"{temp_c}°C — life-threatening heat"})
            overall = "extreme"
        elif temp_c >= 35:
            risks.append({"hazard": "heatwave", "level": "high", "detail": f"{temp_c}°C — dangerous heat, limit outdoor exposure"})
            overall = max(overall, "high", key=_risk_order)
        elif temp_c >= 30:
            risks.append({"hazard": "hot", "level": "moderate", "detail": f"{temp_c}°C — stay hydrated, seek shade"})
            overall = max(overall, "moderate", key=_risk_order)
        elif temp_c < -20:
            risks.append({"hazard": "extreme_cold", "level": "extreme", "detail": f"{temp_c}°C — life-threatening cold"})
            overall = "extreme"
        elif temp_c < -10:
            risks.append({"hazard": "severe_cold", "level": "high", "detail": f"{temp_c}°C — risk of frostbite and hypothermia"})
            overall = max(overall, "high", key=_risk_order)
        elif temp_c < 0:
            risks.append({"hazard": "cold", "level": "moderate", "detail": f"{temp_c}°C — dress warmly, watch for ice"})
            overall = max(overall, "moderate", key=_risk_order)

        # Wind risks
        if wind_kmh >= 120:
            risks.append({"hazard": "hurricane_force_wind", "level": "extreme", "detail": f"{wind_kmh} km/h — catastrophic wind"})
            overall = "extreme"
        elif wind_kmh >= 80:
            risks.append({"hazard": "severe_gale", "level": "high", "detail": f"{wind_kmh} km/h — structural damage possible"})
            overall = max(overall, "high", key=_risk_order)
        elif wind_kmh >= 50:
            risks.append({"hazard": "strong_wind", "level": "moderate", "detail": f"{wind_kmh} km/h — secure loose items, difficult driving"})
            overall = max(overall, "moderate", key=_risk_order)

        # Precipitation risks
        if precip_mm >= 100:
            risks.append({"hazard": "extreme_rainfall", "level": "extreme", "detail": f"{precip_mm}mm — catastrophic flooding possible"})
            overall = "extreme"
        elif precip_mm >= 50:
            risks.append({"hazard": "heavy_rain", "level": "high", "detail": f"{precip_mm}mm — flooding risk, avoid travel"})
            overall = max(overall, "high", key=_risk_order)
        elif precip_mm >= 25:
            risks.append({"hazard": "moderate_rain", "level": "moderate", "detail": f"{precip_mm}mm — localised flooding possible"})
            overall = max(overall, "moderate", key=_risk_order)

        # Thunderstorm detection from weather code string
        wc_lower = str(weather_code).lower()
        if any(kw in wc_lower for kw in ["thunderstorm", "thunder", "lightning", "tornado"]):
            risks.append({"hazard": "thunderstorm", "level": "high", "detail": "Active thunderstorm — seek shelter immediately"})
            overall = max(overall, "high", key=_risk_order)

        if not risks:
            risks.append({"hazard": "none", "level": "low", "detail": "No significant weather hazards detected"})

        return OrchidToolOutput(result={
            "overall_risk": overall,
            "risks": risks,
            "summary": _risk_summary(overall),
        })


def _risk_order(level: str) -> int:
    return {"low": 0, "moderate": 1, "high": 2, "extreme": 3}.get(level, 0)


def _risk_summary(level: str) -> str:
    summaries = {
        "low": "Conditions are normal. No special precautions needed.",
        "moderate": "Some weather hazards present. Take basic precautions and stay informed.",
        "high": "Dangerous weather conditions. Limit outdoor activities, prepare emergency supplies, and monitor official alerts.",
        "extreme": "Life-threatening weather conditions. Seek shelter immediately and follow emergency services instructions.",
    }
    return summaries.get(level, summaries["low"])
