from __future__ import annotations

from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

_DEMOGRAPHICS: dict[str, dict[str, Any]] = {
    "indie rock": {"age_range": "18-35", "gender_split": "55% M / 45% F", "avg_ticket_price_sensitivity": "medium", "social_platforms": ["Instagram", "TikTok", "Spotify"]},
    "electronic": {"age_range": "18-28", "gender_split": "60% M / 40% F", "avg_ticket_price_sensitivity": "low", "social_platforms": ["TikTok", "Instagram", "SoundCloud"]},
    "world": {"age_range": "25-50", "gender_split": "48% M / 52% F", "avg_ticket_price_sensitivity": "high", "social_platforms": ["Facebook", "Instagram", "Spotify"]},
    "post-punk": {"age_range": "25-45", "gender_split": "58% M / 42% F", "avg_ticket_price_sensitivity": "medium", "social_platforms": ["Instagram", "YouTube", "Bandcamp"]},
    "dream pop": {"age_range": "20-30", "gender_split": "40% M / 60% F", "avg_ticket_price_sensitivity": "low", "social_platforms": ["TikTok", "Instagram", "Spotify"]},
    "house": {"age_range": "21-35", "gender_split": "55% M / 45% F", "avg_ticket_price_sensitivity": "low", "social_platforms": ["Instagram", "TikTok", "RA Guide"]},
}

_PRICING_TIERS: dict[str, dict[str, Any]] = {
    "early_bird": {"price": 89, "target_sales": 3000, "release_window": "4 months before"},
    "general": {"price": 129, "target_sales": 8000, "release_window": "3 months before"},
    "late": {"price": 159, "target_sales": 4000, "release_window": "1 month before"},
    "vip": {"price": 249, "target_sales": 800, "release_window": "3 months before"},
}

_CHANNELS: list[dict[str, Any]] = [
    {"name": "Instagram Ads", "cpm": 6.50, "best_for": "visual-heavy lineup reveals, behind-the-scenes content"},
    {"name": "TikTok Campaign", "cpm": 4.20, "best_for": "EDM/dance acts, viral challenges, UGC campaigns"},
    {"name": "Spotify Audio Ads", "cpm": 15.00, "best_for": "genre-targeted artist promotion, playlist takeovers"},
    {"name": "Meta / Facebook Ads", "cpm": 8.00, "best_for": "older demographics, event pages, retargeting"},
    {"name": "Influencer Partnerships", "cost_estimate": "2K-15K per partnership", "best_for": "credibility, niche genre communities"},
    {"name": "Local Radio", "cost_estimate": "1K-5K per station", "best_for": "regional awareness, last-minute ticket push"},
]


def _tool_kwargs(tool_input: OrchidToolInput) -> dict[str, Any]:
    kwargs = dict(tool_input.parameters)
    kwargs.setdefault("query", tool_input.query)
    kwargs.setdefault("context", tool_input.context)
    kwargs.setdefault("auth_context", tool_input.auth_context)
    kwargs.setdefault("content_sources", tool_input.content_sources)
    return kwargs


def analyze_demographics(genre: str = "", **kwargs: Any) -> dict[str, Any]:
    genre_lower = genre.lower().strip()
    if genre_lower in _DEMOGRAPHICS:
        return {"genre": genre, "demographics": _DEMOGRAPHICS[genre_lower]}
    return {"error": f"No data for genre '{genre}'", "available_genres": list(_DEMOGRAPHICS)}


def get_pricing_strategy(estimated_attendance: int = 15000, **kwargs: Any) -> dict[str, Any]:
    tiers = {}
    for name, tier in _PRICING_TIERS.items():
        tiers[name] = {
            "price": tier["price"],
            "projected_revenue": tier["price"] * tier["target_sales"],
            "target_sales": tier["target_sales"],
            "window": tier["release_window"],
        }
    return {
        "tiers": tiers,
        "total_projected_revenue": sum(t["projected_revenue"] for t in tiers.values()),
        "estimated_attendance": estimated_attendance,
    }


def recommend_channels(genres: str = "", budget: int = 50000, **kwargs: Any) -> dict[str, Any]:
    genre_list = [g.strip().lower() for g in genres.split(",")]
    recommendations = []
    for channel in _CHANNELS:
        score = 0
        for genre in genre_list:
            if genre in _DEMOGRAPHICS and channel["name"].lower().replace(" ", "") in str(_DEMOGRAPHICS[genre]["social_platforms"]).lower():
                score += 2
        recommendations.append({**channel, "relevance_score": score})

    recommendations.sort(key=lambda c: c["relevance_score"], reverse=True)
    return {
        "budget": budget,
        "genres": genre_list,
        "recommended_channels": [r for r in recommendations if r["relevance_score"] > 0],
        "all_channels": recommendations,
    }


def project_attendance(lineup_size: int = 10, avg_draw: int = 12000, **kwargs: Any) -> dict[str, Any]:
    base = lineup_size * avg_draw // 3
    return {
        "projected_attendance": base,
        "confidence": "medium",
        "factors": {
            "lineup_count": lineup_size,
            "average_artist_draw": avg_draw,
            "weather_factor": "30% of attendees are weather-dependent",
            "competition_factor": "Check local events within 100km radius",
        },
        "ticket_revenue_estimate": {
            f"at {tier['price']} EUR avg": base * tier["price"]
            for name, tier in list(_PRICING_TIERS.items())[:2]
        },
    }


class AnalyzeDemographicsTool(OrchidTool):
    name = "analyze_demographics"
    description = "Analyze target demographics for a music genre"
    parameters_schema = {
        "type": "object",
        "properties": {
            "genre": {
                "type": "string",
                "description": "Music genre (e.g. 'indie rock')",
                "default": "",
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=analyze_demographics(**_tool_kwargs(tool_input)))


class GetPricingStrategyTool(OrchidTool):
    name = "get_pricing_strategy"
    description = "Get pricing strategy: early bird, general, late, VIP tiers with revenue projections"
    parameters_schema = {
        "type": "object",
        "properties": {
            "estimated_attendance": {
                "type": "integer",
                "description": "Estimated total attendance",
                "default": 15000,
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=get_pricing_strategy(**_tool_kwargs(tool_input)))


class RecommendChannelsTool(OrchidTool):
    name = "recommend_channels"
    description = "Recommend marketing channels based on lineup genres and budget"
    parameters_schema = {
        "type": "object",
        "properties": {
            "genres": {
                "type": "string",
                "description": "Comma-separated genres (e.g. 'indie rock,electronic')",
                "default": "",
            },
            "budget": {
                "type": "integer",
                "description": "Marketing budget in USD",
                "default": 50000,
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=recommend_channels(**_tool_kwargs(tool_input)))


class ProjectAttendanceTool(OrchidTool):
    name = "project_attendance"
    description = "Project attendance based on lineup size and average artist draw"
    parameters_schema = {
        "type": "object",
        "properties": {
            "lineup_size": {
                "type": "integer",
                "description": "Number of artists on the lineup",
                "default": 10,
            },
            "avg_draw": {
                "type": "integer",
                "description": "Average attendance draw per artist",
                "default": 12000,
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=project_attendance(**_tool_kwargs(tool_input)))
