from __future__ import annotations

from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

_ARTISTS: dict[str, dict[str, Any]] = {
    "the midnight vibrations": {
        "name": "The Midnight Vibrations",
        "genre": "Indie Rock / Shoegaze",
        "members": 4,
        "typical_fee": 85000,
        "availability": "Q2-Q3 2027",
        "stage_preference": "Main Stage",
        "power_requirement": "32A three-phase",
        "rider_notes": "2 dressing rooms, vegan catering, professional backline",
        "tour_status": "Headlining European summer 2027",
        "avg_attendance_draw": 22000,
        "social_following": "2.4M combined",
    },
    "aurora flux": {
        "name": "Aurora Flux",
        "genre": "Electronic / Synthwave",
        "members": 2,
        "typical_fee": 45000,
        "availability": "Q1-Q4 2027 (selective dates)",
        "stage_preference": "Electronic Tent",
        "power_requirement": "16A single-phase + 2x 32A for LED rig",
        "rider_notes": "Blackout backstage, still water only, custom stage lighting plot",
        "tour_status": "New album cycle starting March 2027",
        "avg_attendance_draw": 12000,
        "social_following": "890K combined",
    },
    "dj kaleidoscope": {
        "name": "DJ Kaleidoscope",
        "genre": "House / Deep Tech",
        "members": 1,
        "typical_fee": 25000,
        "availability": "Q2-Q3 2027",
        "stage_preference": "Electronic Tent or Late Night Arena",
        "power_requirement": "16A single-phase",
        "rider_notes": "Pioneer DJM-V10 + 3x CDJ-3000, 2 monitors, 1 bottle premium vodka",
        "tour_status": "Ibiza residency June-September 2027",
        "avg_attendance_draw": 8000,
        "social_following": "1.2M combined",
    },
    "solar eclipse collective": {
        "name": "Solar Eclipse Collective",
        "genre": "World / Afrobeat / Jazz Fusion",
        "members": 12,
        "typical_fee": 120000,
        "availability": "Q3 2027 only",
        "stage_preference": "Main Stage or World Music Stage",
        "power_requirement": "32A three-phase + 16A for monitors",
        "rider_notes": "Professional backline, 3 dressing rooms, catering for 20, on-site percussion tech",
        "tour_status": "World tour 2027 — few festival slots",
        "avg_attendance_draw": 35000,
        "social_following": "5.1M combined",
    },
    "neon cathedral": {
        "name": "Neon Cathedral",
        "genre": "Post-Punk / Gothic Rock",
        "members": 5,
        "typical_fee": 60000,
        "availability": "Q1-Q3 2027",
        "stage_preference": "Second Stage",
        "power_requirement": "32A three-phase",
        "rider_notes": "Dark backstage lighting, incense, organic catering, vintage amps available",
        "tour_status": "Reunion tour 2027",
        "avg_attendance_draw": 15000,
        "social_following": "3.8M combined",
    },
    "luna & the tides": {
        "name": "Luna & The Tides",
        "genre": "Dream Pop / Indie Folk",
        "members": 3,
        "typical_fee": 35000,
        "availability": "Q1-Q2 2027",
        "stage_preference": "Acoustic Garden or Second Stage",
        "power_requirement": "16A single-phase",
        "rider_notes": "Natural light preferred, herbal tea selection, acoustic treatment panels",
        "tour_status": "Album launch Q2 2027",
        "avg_attendance_draw": 5000,
        "social_following": "450K combined",
    },
}


def _tool_kwargs(tool_input: OrchidToolInput) -> dict[str, Any]:
    kwargs = dict(tool_input.parameters)
    kwargs.setdefault("query", tool_input.query)
    kwargs.setdefault("context", tool_input.context)
    kwargs.setdefault("auth_context", tool_input.auth_context)
    kwargs.setdefault("content_sources", tool_input.content_sources)
    return kwargs


def lookup_artist(artist_name: str = "", **kwargs: Any) -> dict[str, Any]:
    matches = [v for k, v in _ARTISTS.items() if artist_name.lower() in k or k in artist_name.lower()]
    if matches:
        return matches[0]
    return {"error": f"Artist '{artist_name}' not found. Available: {', '.join(_ARTISTS)}"}


def list_available_artists(quarter: str = "", max_fee: int = 150000, **kwargs: Any) -> dict[str, Any]:
    results = {}
    for key, artist in _ARTISTS.items():
        if quarter and quarter.upper() not in artist["availability"]:
            continue
        if max_fee and artist["typical_fee"] > max_fee:
            continue
        results[key] = {
            "name": artist["name"],
            "fee": artist["typical_fee"],
            "availability": artist["availability"],
            "genre": artist["genre"],
        }
    return {"artists": results, "count": len(results), "quarter_filter": quarter or "all"}


def get_rider_details(artist_name: str = "", **kwargs: Any) -> dict[str, Any]:
    for key, artist in _ARTISTS.items():
        if artist_name.lower() in key or key in artist_name.lower():
            return {
                "name": artist["name"],
                "stage_preference": artist["stage_preference"],
                "power_requirement": artist["power_requirement"],
                "rider_notes": artist["rider_notes"],
            }
    return {"error": f"Artist '{artist_name}' not found"}


def compare_artists(artist_a: str = "", artist_b: str = "", **kwargs: Any) -> dict[str, Any]:
    a = next((v for k, v in _ARTISTS.items() if artist_a.lower() in k or k in artist_a.lower()), None)
    b = next((v for k, v in _ARTISTS.items() if artist_b.lower() in k or k in artist_b.lower()), None)
    if not a or not b:
        return {"error": "One or both artists not found", "artist_a": bool(a), "artist_b": bool(b)}
    return {
        "comparison": {
            "artist_a": {"name": a["name"], "fee": a["typical_fee"], "draw": a["avg_attendance_draw"]},
            "artist_b": {"name": b["name"], "fee": b["typical_fee"], "draw": b["avg_attendance_draw"]},
            "fee_difference": abs(a["typical_fee"] - b["typical_fee"]),
            "draw_advantage": "a" if a["avg_attendance_draw"] > b["avg_attendance_draw"] else "b",
        }
    }


class LookupArtistTool(OrchidTool):
    name = "lookup_artist"
    description = "Look up an artist by name: genre, fee, availability, rider requirements"
    parameters_schema = {
        "type": "object",
        "properties": {
            "artist_name": {
                "type": "string",
                "description": "Artist name (e.g. 'The Midnight Vibrations')",
                "default": "",
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=lookup_artist(**_tool_kwargs(tool_input)))


class ListAvailableArtistsTool(OrchidTool):
    name = "list_available_artists"
    description = "List artists available for a given quarter, optionally filtered by max fee"
    parameters_schema = {
        "type": "object",
        "properties": {
            "quarter": {
                "type": "string",
                "description": "Quarter to filter (e.g. 'Q2 2027')",
                "default": "",
            },
            "max_fee": {
                "type": "integer",
                "description": "Maximum fee in USD",
                "default": 150000,
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=list_available_artists(**_tool_kwargs(tool_input)))


class GetRiderDetailsTool(OrchidTool):
    name = "get_rider_details"
    description = "Get technical rider: stage preference, power requirements, backstage needs"
    parameters_schema = {
        "type": "object",
        "properties": {
            "artist_name": {
                "type": "string",
                "description": "Artist name",
                "default": "",
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=get_rider_details(**_tool_kwargs(tool_input)))


class CompareArtistsTool(OrchidTool):
    name = "compare_artists"
    description = "Compare two artists side-by-side: fee, draw, genre"
    parameters_schema = {
        "type": "object",
        "properties": {
            "artist_a": {
                "type": "string",
                "description": "First artist name",
                "default": "",
            },
            "artist_b": {
                "type": "string",
                "description": "Second artist name",
                "default": "",
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=compare_artists(**_tool_kwargs(tool_input)))
